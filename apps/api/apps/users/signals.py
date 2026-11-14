"""
Django signals for user-related models.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User, NotificationSettings


@receiver(post_save, sender=User)
def create_user_notification_settings(sender, instance, created, **kwargs):
    """
    Create default notification settings when a new user is created.
    """
    if created:
        NotificationSettings.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_notification_settings(sender, instance, **kwargs):
    """
    Ensure notification settings exist for all users.
    """
    if not hasattr(instance, 'notification_settings'):
        NotificationSettings.objects.create(user=instance)


@receiver(post_save, sender=User)
def create_user_default_subscription(sender, instance, created, **kwargs):
    """
    Cria a assinatura do plano Gratuito para cada utilizador novo (mesmo helper
    usado em todo o lado: sem fim e com as vidas do plano Gratuito).
    """
    if created:
        try:
            from apps.subscriptions.services import obter_ou_criar_assinatura
            obter_ou_criar_assinatura(instance)
        except Exception as e:
            # Não impedir a criação do utilizador
            import logging
            logging.getLogger(__name__).error(
                'Falha ao criar a assinatura Gratuita do utilizador %s: %s', instance.id, e)
