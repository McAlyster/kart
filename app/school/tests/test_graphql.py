import json

import graphene
from graphene_django.utils.testing import GraphQLTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token

from kart.schema import Query
from school.tests.factories import (
    ScienceStudentFactory,
    StudentApplicationFactory,
    StudentFactory,
    TeachingArtistFactory,
)
from utils.tests.factories import UserFactory
from utils.tests.utils import obtain_jwt_token


class TestGQLPages(GraphQLTestCase):
    """
    TODO: do tests
    """

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_page_candidature_results_list(self):
        # TEST WITH JWT
        # create value
        StudentApplicationFactory()
        # auth user
        user = UserFactory()
        user.is_staff = True
        user.save()
        jwt = obtain_jwt_token(user)
        # get infos
        candidature_results_list_url = reverse("candidatureResultsList_gql")
        response = self.client.get(candidature_results_list_url, HTTP_AUTHORIZATION="JWT {}".format(jwt["access"]))

        results = json.loads(response.content)
        self.assertFalse(hasattr(results, "errors"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_page_candidature_results_list_with_token(self):
        # TEST WITH TOKEN
        # create value
        StudentApplicationFactory()
        # auth user
        user = UserFactory()
        user.is_staff = True
        user.save()
        token = Token.objects.create(user=user)
        token.save()
        # get infos
        candidature_results_list_url = reverse("candidatureResultsList_gql")
        response = self.client.get(candidature_results_list_url, HTTP_AUTHORIZATION=f"TOKEN {token}")

        results = json.loads(response.content)
        self.assertFalse(hasattr(results, "errors"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_query_promotions(self):
        # create objects
        self.student = StudentFactory()
        # query
        query = "query {\
                    promotions {\
                    name\
                    picture\
                    startingYear\
                    endingYear\
                    students {\
                        id\
                        displayName\
                    }\
                    }\
                }"
        # execute query
        schema = graphene.Schema(query=Query)
        result = schema.execute(query)
        self.assertIsNone(result.errors)

    def test_query_studentx(self):
        self.student = StudentFactory(diploma_mention="Mention", diploma_file="path/to/diploma.pdf")
        query = "query StudentX($etudiantID: Int) {\
                    student(id: $etudiantID) {\
                        diplomaMention\
                        diplomaFile\
                        displayName\
                        photo\
                        gender\
                        birthdate\
                        birthplace\
                        birthplaceCountry\
                        deathdate\
                        deathplace\
                        deathplaceCountry\
                        bioShortFr\
                        bioShortEn\
                        bioFr\
                        bioEn\
                        cursus\
                        promotion {\
                            name\
                            startingYear\
                            endingYear\
                        }\
                        websites {\
                            titleFr\
                            url\
                        }\
                        artworks {\
                            id\
                            title\
                            picture\
                            type\
                            productionDate\
                            diffusion {\
                                event {\
                                    title\
                                    id\
                                }\
                            }\
                        }\
                    }\
                }"
        schema = graphene.Schema(query=Query)
        result = schema.execute(query, variables={"etudiantID": self.student.id})
        self.assertIsNotNone(result.errors)
        self.assertEqual(result.data["student"]["diplomaMention"], self.student.diploma_mention)
        self.assertEqual(result.data["student"]["diplomaFile"], None)

    def test_query_studentx_with_staff_auth(self):
        student = StudentFactory(diploma_mention="Mention", diploma_file="path/to/diploma.pdf")
        user_staff = UserFactory(is_staff=True)

        # Authentifie directement le client de test
        self.client.force_login(user_staff)

        query = """
            query StudentX($etudiantID: Int!) {
                student(id: $etudiantID) {
                    diplomaMention
                    diplomaFile
                }
            }
        """

        response = self.query(query, variables={"etudiantID": student.id})

        content = response.json()
        self.assertNotIn("errors", content)
        self.assertEqual(content["data"]["student"]["diplomaMention"], student.diploma_mention)

    def test_page_teaching_artists_list(self):
        # create value
        TeachingArtistFactory()
        teaching_artists_list_url = reverse("teachingArtistsList_gql")
        response = self.client.get(teaching_artists_list_url)

        teachers = json.loads(response.content)

        self.assertFalse(hasattr(teachers, "errors"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_query_professorx(self):
        teacher = TeachingArtistFactory()
        query = "query ProfessorX($professorID: Int) {\
                    teachingArtist(id: $professorID) {\
                        displayName\
                        gender\
                        photo\
                        birthplace\
                        birthplaceCountry\
                        birthdate\
                        deathdate\
                        deathplace\
                        deathplaceCountry\
                        presentationTextFr\
                        presentationTextEn\
                        cursus\
                        residenceCountry\
                        residenceTown\
                    }\
                }"
        schema = graphene.Schema(query=Query)
        result = schema.execute(query, variables={"professorID": teacher.id})
        self.assertIsNone(result.errors)

    def test_query_sciencestudentx(self):
        science_student = ScienceStudentFactory()
        query = "query ScienceStudentX($scienceStudentID: Int) {\
                    scienceStudent(id: $scienceStudentID) {\
                        student {\
                            id\
                            displayName\
                            photo\
                            gender\
                            birthdate\
                            birthplace\
                            birthplaceCountry\
                            deathdate\
                            deathplace\
                            deathplaceCountry\
                            bioShortFr\
                            bioShortEn\
                            bioFr\
                            bioEn\
                            cursus\
                            promotion {\
                                name\
                                startingYear\
                                endingYear\
                            }\
                        }\
                    }\
                }"
        schema = graphene.Schema(query=Query)
        result = schema.execute(query, variables={"scienceStudentID": science_student.id})
        self.assertIsNone(result.errors)
