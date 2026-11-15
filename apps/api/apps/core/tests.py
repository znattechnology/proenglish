"""
Tests for core functionality.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status
from apps.core.models import Address, BaseModel

User = get_user_model()


class AddressModelTest(TestCase):
    """Test Address model functionality."""
    
    def setUp(self):
        self.address = Address.objects.create(
            street='Rua Test 123',
            city='Lisboa',
            postal_code='1000-001',
            district='Lisboa',
            country='Portugal'
        )
    
    def test_address_creation(self):
        """Test address creation."""
        self.assertEqual(self.address.street, 'Rua Test 123')
        self.assertEqual(self.address.city, 'Lisboa')
        self.assertEqual(self.address.postal_code, '1000-001')
        self.assertEqual(self.address.district, 'Lisboa')
        self.assertEqual(self.address.country, 'Portugal')
    
    def test_address_str_representation(self):
        """Test address string representation."""
        expected = 'Rua Test 123, Lisboa, 1000-001'
        self.assertEqual(str(self.address), expected)
    
    def test_full_address_property(self):
        """Test full_address property."""
        self.address.building_number = '123A'
        self.address.apartment = '2B'
        self.address.floor = '2'
        self.address.save()
        
        full_address = self.address.full_address
        self.assertIn('Rua Test 123 123A', full_address)
        self.assertIn('Apt 2B', full_address)
        self.assertIn('Floor 2', full_address)
        self.assertIn('Lisboa', full_address)
        self.assertIn('Portugal', full_address)
    
    def test_address_optional_fields(self):
        """Test address with optional fields."""
        address_with_extras = Address.objects.create(
            street='Avenida da República',
            city='Porto',
            postal_code='4000-001',
            district='Porto',
            building_number='456',
            apartment='3C',
            floor='3',
            additional_info='Próximo ao metro'
        )
        
        self.assertEqual(address_with_extras.building_number, '456')
        self.assertEqual(address_with_extras.apartment, '3C')
        self.assertEqual(address_with_extras.floor, '3')
        self.assertEqual(address_with_extras.additional_info, 'Próximo ao metro')


class BaseModelTest(TestCase):
    """Test BaseModel functionality."""
    
    def setUp(self):
        # Create user and address to test BaseModel features
        self.user = User.objects.create_user(
            email='base@test.com',
            name='Base User',
            password='testpass'
        )
        self.address = Address.objects.create(
            street='Test Street',
            city='Test City',
            postal_code='12345',
            district='Test District'
        )
    
    def test_base_model_uuid_field(self):
        """Test that BaseModel has UUID primary key."""
        # Test with User model which extends BaseModel
        self.assertIsNotNone(self.user.id)
        # ID should be UUID (36 characters with hyphens)
        self.assertEqual(len(str(self.user.id)), 36)
        
        # Test with Address model which also extends BaseModel
        self.assertIsNotNone(self.address.id)
        self.assertEqual(len(str(self.address.id)), 36)
    
    def test_base_model_timestamp_fields(self):
        """Test that BaseModel has timestamp fields."""
        # User model test
        self.assertIsNotNone(self.user.created_at)
        self.assertIsNotNone(self.user.updated_at)
        
        # Address model test
        self.assertIsNotNone(self.address.created_at)
        self.assertIsNotNone(self.address.updated_at)
    
    def test_updated_at_changes(self):
        """Test that updated_at changes when model is saved."""
        original_updated = self.user.updated_at
        
        # Update the user
        self.user.name = 'Updated Name'
        self.user.save()
        
        self.assertGreater(self.user.updated_at, original_updated)
        
        # Test with address as well
        original_address_updated = self.address.updated_at
        self.address.city = 'Updated City'
        self.address.save()
        
        self.assertGreater(self.address.updated_at, original_address_updated)


class CoreHealthTest(APITestCase):
    """Test core health check functionality."""
    
    def test_health_check_available(self):
        """Test that health check functionality exists."""
        # Since we don't have the upload URLs, we'll test basic functionality
        # This ensures the core app can be imported without errors
        from apps.core import models
        from apps.core import exceptions
        
        # Test that core models can be imported
        self.assertTrue(hasattr(models, 'BaseModel'))
        self.assertTrue(hasattr(models, 'Address'))
        self.assertTrue(hasattr(models, 'UUIDModel'))
        self.assertTrue(hasattr(models, 'TimestampedModel'))
        
        # Test that exceptions module exists
        self.assertTrue(hasattr(exceptions, 'custom_exception_handler'))


class CoreExceptionsTest(TestCase):
    """Test core exception handling."""
    
    def test_exception_handler_import(self):
        """Test that custom exception handler can be imported."""
        from apps.core.exceptions import custom_exception_handler
        
        self.assertIsNotNone(custom_exception_handler)
        self.assertTrue(callable(custom_exception_handler))
    
    def test_custom_exception_classes(self):
        """Test custom exception classes."""
        from apps.core.exceptions import APIException, ValidationError, NotFoundError, PermissionError
        
        # Test that custom exceptions can be instantiated
        api_exc = APIException("Test error")
        self.assertEqual(api_exc.message, "Test error")
        
        validation_exc = ValidationError("Validation failed")
        self.assertEqual(validation_exc.message, "Validation failed")
        
        not_found_exc = NotFoundError("Not found")
        self.assertEqual(not_found_exc.message, "Not found")
        
        permission_exc = PermissionError("Permission denied")
        self.assertEqual(permission_exc.message, "Permission denied")

class ArmazenamentoDjango52Test(TestCase):
    """
    O Django 5.1 removeu DEFAULT_FILE_STORAGE e STATICFILES_STORAGE e passou a ignorá-los sem erro.
    Com USE_S3=True os ficheiros têm de ir para o S3 pela definição STORAGES (core/settings.py).
    Lê as definições num processo à parte, com o ambiente controlado; não fala com o S3.
    """

    def ler_storages(self, use_s3):
        import json
        import os
        import subprocess
        import sys
        from django.conf import settings
        env = {**os.environ, 'USE_S3': 'True' if use_s3 else 'False', 'DJANGO_SETTINGS_MODULE': 'core.settings'}
        codigo = ('import json, django; django.setup(); from django.conf import settings as s; '
                  'from django.core.files.storage import storages; '
                  'print(json.dumps({"storages": s.STORAGES, "default": type(storages["default"]).__name__, '
                  '"antigas": [n for n in ("DEFAULT_FILE_STORAGE", "STATICFILES_STORAGE") if hasattr(s, n)]}))')
        r = subprocess.run([sys.executable, '-c', codigo], cwd=str(settings.BASE_DIR), env=env,
                           capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        return json.loads(r.stdout.strip().splitlines()[-1])

    def test_com_s3_os_ficheiros_vao_para_o_s3(self):
        d = self.ler_storages(True)
        self.assertEqual(d['storages']['default']['BACKEND'], 'storages.backends.s3boto3.S3Boto3Storage')
        self.assertEqual(d['storages']['staticfiles']['BACKEND'], 'storages.backends.s3boto3.S3Boto3Storage')
        self.assertIn(d['default'], ('S3Storage', 'S3Boto3Storage'))  # S3Boto3Storage é o nome antigo de S3Storage
        self.assertEqual(d['antigas'], [])

    def test_atras_do_proxy_o_https_e_reconhecido(self):
        import json
        import os
        import subprocess
        import sys
        from django.conf import settings
        codigo = ('import json, django; django.setup(); from django.conf import settings as s; '
                  'print(json.dumps(getattr(s, "SECURE_PROXY_SSL_HEADER", None)))')
        for proxy, esperado in (('True', ['HTTP_X_FORWARDED_PROTO', 'https']), ('False', None)):
            env = {**os.environ, 'TRUSTED_PROXY': proxy, 'DJANGO_SETTINGS_MODULE': 'core.settings'}
            r = subprocess.run([sys.executable, '-c', codigo], cwd=str(settings.BASE_DIR), env=env,
                               capture_output=True, text=True, timeout=120)
            self.assertEqual(r.returncode, 0, r.stderr[-2000:])
            self.assertEqual(json.loads(r.stdout.strip().splitlines()[-1]), esperado, proxy)

    def test_sem_s3_ficam_no_disco(self):
        d = self.ler_storages(False)
        self.assertEqual(d['storages']['default']['BACKEND'], 'django.core.files.storage.FileSystemStorage')
        self.assertEqual(d['default'], 'FileSystemStorage')
