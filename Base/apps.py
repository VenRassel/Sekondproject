from django.apps import AppConfig

class BaseConfig(AppConfig):
    name = 'Base'

    def ready(self):
        import Base.signals
