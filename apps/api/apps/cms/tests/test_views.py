"""As rotas antigas do CMS foram substituídas por /api/v1/site/ e respondem 410."""
from django.test import TestCase


class RotasAntigasTests(TestCase):
    def test_respondem_410(self):
        for url in ('/api/v1/cms/landing-page-data/', '/api/v1/cms/hero/', '/api/v1/cms/faqs/1/'):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 410, url)
            self.assertEqual(r.json()['code'], 'endpoint_removido')
        self.assertEqual(self.client.post('/api/v1/cms/hero/', {}).status_code, 410)
