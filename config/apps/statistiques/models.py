from django.db import models


class StatistiqueRegionale(models.Model):
    region = models.CharField(max_length=40)
    annee = models.PositiveSmallIntegerField()
    population = models.PositiveBigIntegerField()
    taux_urbanisation_pct = models.DecimalField(max_digits=5, decimal_places=2)
    taux_alphabetisation_pct = models.DecimalField(max_digits=5, decimal_places=2)
    taux_chomage_pct = models.DecimalField(max_digits=5, decimal_places=2)
    taux_pauvrete_pct = models.DecimalField(max_digits=5, decimal_places=2)
    acces_internet_pct = models.DecimalField(max_digits=5, decimal_places=2)
    centres_sante = models.PositiveIntegerField()
    taux_scolarisation_pct = models.DecimalField(max_digits=5, decimal_places=2)
    production_cerealiere_tonnes = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["region", "annee"], name="unique_region_annee")
        ]

    def __str__(self):
        return f"{self.region} - {self.annee}"
