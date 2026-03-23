from django.test import TestCase
from faker import Faker


class FakerIntegrationTest(TestCase):

    def setUp(self):
        self.fake = Faker('pt_BR')

    def test_faker_generates_valid_cpf(self):
        cpf = self.fake.cpf()
        # CPF com pontuação tem 14 caracteres (XXX.XXX.XXX-XX)
        self.assertEqual(len(cpf), 14)

    def test_faker_generates_name(self):
        name = self.fake.name()
        self.assertTrue(len(name) > 0)

    def test_faker_generates_different_names(self):
        names = {self.fake.name() for _ in range(50)}
        self.assertGreater(len(names), 1)

    def test_faker_generates_different_cpfs(self):
        cpfs = {self.fake.cpf() for _ in range(50)}
        self.assertGreater(len(cpfs), 1)