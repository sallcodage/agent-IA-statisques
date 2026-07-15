from django.contrib import admin

from config.apps.statistiques.models import StatistiqueRegionale


@admin.register(StatistiqueRegionale)
class StatistiqueRegionaleAdmin(admin.ModelAdmin):
    list_display = ("region", "annee", "population", "acces_internet_pct")
    search_fields = ("region",)
