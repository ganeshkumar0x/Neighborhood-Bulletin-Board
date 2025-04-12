import graphene
from graphene import ObjectType, String, List, Field, Mutation, Boolean
from pymongo import MongoClient
from neomodel import config, StructuredNode, StringProperty, RelationshipTo, db
import bcrypt
from datetime import datetime
from bson import ObjectId

MONGO_URI = "mongodb://localhost:27017/"
MONGO_DB_NAME = "neighborhood_board"

client = MongoClient(MONGO_URI)
db_mongo = client[MONGO_DB_NAME]

users_collection = db_mongo["users"]
posts_collection = db_mongo["posts"]
categories_collection = db_mongo["categories"]

config.DATABASE_URL = "bolt://neo4j:1234@localhost:7687"

class UserNode(StructuredNode):
    user_id = StringProperty(unique_index=True)
    username = StringProperty()
    posted = RelationshipTo("PostNode", "POSTED")
    accepted = RelationshipTo("PostNode", "ACCEPTED")

class PostNode(StructuredNode):
    post_id = StringProperty(unique_index=True)
    title = StringProperty()
    belongs_to = RelationshipTo("CategoryNode", "BELONGS_TO")

class CategoryNode(StructuredNode):
    name = StringProperty(unique_index=True)

class UserType(ObjectType):
    user_id = String()
    username = String()
    email = String()
    location = String()

class PostType(ObjectType):
    post_id = String()
    title = String()
    description = String()
    location = String()
    category = String()
    accepted_by = List(String)

class CategoryType(ObjectType):
    name = String()
    description = String()

class Query(ObjectType):
    all_posts = List(PostType)
    all_users = List(UserType)
    all_categories = List(CategoryType)

    def resolve_all_posts(self, info):
        posts = posts_collection.find()
        return [
            PostType(
                post_id=str(post["_id"]),
                title=post.get("title", ""),
                description=post.get("description", ""),
                location=post.get("location", ""),
                category=post.get("category", ""),
                accepted_by=post.get("accepted_by", [])
            )
            for post in posts
        ]

    def resolve_all_users(self, info):
        users = users_collection.find()
        return [
            UserType(
                user_id=str(user["_id"]),
                username=user.get("username", ""),
                email=user.get("email", ""),
                location=user.get("location", "")
            )
            for user in users
        ]

    def resolve_all_categories(self, info):
        categories = categories_collection.find()
        return [
            CategoryType(
                name=category.get("name", ""),
                description=category.get("description", "")
            )
            for category in categories
        ]

class SignUp(Mutation):
    success = Boolean()
    message = String()

    class Arguments:
        username = String()
        email = String()
        password = String()
        location = String()

    def mutate(self, info, username, email, password, location):
        if users_collection.find_one({"email": email}):
            return SignUp(success=False, message="Email already registered.")

        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        user_data = {
            "username": username,
            "email": email,
            "password": hashed_password,
            "location": location,
        }
        users_collection.insert_one(user_data)

        try:
            user_node = UserNode.nodes.get_or_none(user_id=email)
            if not user_node:
                user_node = UserNode(user_id=email, username=username)
                user_node.save()
        except Exception as e:
            return SignUp(success=False, message=f"Neo4j Error: {str(e)}")

        return SignUp(success=True, message="User registered successfully.")

class SignIn(Mutation):
    success = Boolean()
    message = String()
    username = String()

    class Arguments:
        email = String()
        password = String()

    def mutate(self, info, email, password):
        user = users_collection.find_one({"email": email})
        if not user:
            return SignIn(success=False, message="User not found.")

        if not bcrypt.checkpw(password.encode('utf-8'), user["password"]):
            return SignIn(success=False, message="Incorrect password.")

        return SignIn(success=True, message="Login successful.", username=user["username"])

class CreatePost(Mutation):
    success = Boolean()
    message = String()

    class Arguments:
        user_email = String()
        title = String()
        description = String()
        category = String()
        location = String()

    def mutate(self, info, user_email, title, description, category, location):
        user = users_collection.find_one({"email": user_email})
        if not user:
            return CreatePost(success=False, message="User not found.")

        user_id = str(user["_id"])

        existing_category = categories_collection.find_one({"name": category})

        if not existing_category:
            categories_collection.insert_one({"name": category, "description": "Default description"})

        post = {
            "user_id": user_id,
            "title": title,
            "description": description,
            "category": category,
            "location": location,
            "created_at": datetime.utcnow(),
            "accepted_by": []
        }
        post_id = str(posts_collection.insert_one(post).inserted_id)

        try:
            result, _ = db.cypher_query(
                "MATCH (u:UserNode {user_id: $user_email}) RETURN u",
                {"user_email": user_email}
            )
            if not result:
                return CreatePost(success=False, message="User node not found in Neo4j")

            post_node = PostNode(post_id=post_id, title=title)
            post_node.save()

            db.cypher_query("""
                MATCH (u:UserNode {user_id: $user_email}), (p:PostNode {post_id: $post_id})
                MERGE (u)-[:POSTED]->(p)
            """, {"user_email": user_email, "post_id": post_id})

            db.cypher_query("""
                MATCH (p:PostNode {post_id: $post_id})
                MERGE (c:CategoryNode {name: $category})
                MERGE (p)-[:BELONGS_TO]->(c)
            """, {"post_id": post_id, "category": category})

        except Exception as e:
            return CreatePost(success=False, message=f"Neo4j Error: {str(e)}")

        return CreatePost(success=True, message="Post created successfully.")

class AcceptPost(Mutation):
    success = Boolean()
    message = String()

    class Arguments:
        user_email = String()
        post_id = String()

    def mutate(self, info, user_email, post_id):
        user = users_collection.find_one({"email": user_email})
        if not user:
            return AcceptPost(success=False, message="User not found. Please sign up.")

        post = posts_collection.find_one({"_id": ObjectId(post_id)})
        if not post:
            return AcceptPost(success=False, message="Post not found.")

        posts_collection.update_one(
            {"_id": ObjectId(post_id)}, {"$addToSet": {"accepted_by": user_email}}
        )

        try:
            db.cypher_query("""
                MATCH (u:UserNode {user_id: $user_email}), (p:PostNode {post_id: $post_id})
                MERGE (u)-[:ACCEPTED]->(p)
            """, {"user_email": user_email, "post_id": post_id})

        except Exception as e:
            return AcceptPost(success=False, message=f"Neo4j Error: {str(e)}")

        return AcceptPost(success=True, message="Post accepted successfully.")

class Mutation(ObjectType):
    sign_up = SignUp.Field()
    sign_in = SignIn.Field()
    create_post = CreatePost.Field()
    accept_post = AcceptPost.Field()

schema = graphene.Schema(query=Query, mutation=Mutation)
