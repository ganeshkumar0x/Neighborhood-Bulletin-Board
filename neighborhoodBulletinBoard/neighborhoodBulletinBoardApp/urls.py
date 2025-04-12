from django.urls import path
from django.views.generic import TemplateView
from graphene_django.views import GraphQLView
from neighborhoodBulletinBoardApp.schema import schema

urlpatterns = [
    path('graphql/', GraphQLView.as_view(graphiql=True, schema=schema)),
    path('', TemplateView.as_view(template_name="neighborhoodBulletinBoardApp/index.html"), name='index'),
    path('signup/', TemplateView.as_view(template_name="neighborhoodBulletinBoardApp/signup.html"), name='signup'),
    path('signin/', TemplateView.as_view(template_name="neighborhoodBulletinBoardApp/signin.html"), name='signin'),
    path('home/', TemplateView.as_view(template_name="neighborhoodBulletinBoardApp/home.html"), name='home'),
    path('create-post/', TemplateView.as_view(template_name="neighborhoodBulletinBoardApp/create_post.html"), name='create_post'),
]
