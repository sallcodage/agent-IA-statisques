import csv
import os
import tempfile
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase

from config.apps.statistiques.models import StatistiqueRegionale
from config.apps.statistiques.services import execute_intent, extract_intent, get_dashboard_metrics


class StatistiquesImportTests(TestCase):
    def test_import_creates_and_updates_rows_without_duplicates(self):
        with tempfile.NamedTemporaryFile("w", newline="", suffix=".csv", delete=False) as handle:
            writer = csv.DictWriter(handle, fieldnames=[
                "region", "annee", "population", "taux_urbanisation_pct",
                "taux_alphabetisation_pct", "taux_chomage_pct", "taux_pauvrete_pct",
                "acces_internet_pct", "centres_sante", "taux_scolarisation_pct",
                "production_cerealiere_tonnes"
            ])
            writer.writeheader()
            writer.writerow({
                "region": "Dakar", "annee": 2024, "population": 4000000,
                "taux_urbanisation_pct": 85.5, "taux_alphabetisation_pct": 90.1,
                "taux_chomage_pct": 10.2, "taux_pauvrete_pct": 8.3,
                "acces_internet_pct": 80.4, "centres_sante": 120,
                "taux_scolarisation_pct": 95.7, "production_cerealiere_tonnes": 50000,
            })
            writer.writerow({
                "region": "Dakar", "annee": 2024, "population": 4100000,
                "taux_urbanisation_pct": 86.0, "taux_alphabetisation_pct": 90.5,
                "taux_chomage_pct": 10.0, "taux_pauvrete_pct": 8.1,
                "acces_internet_pct": 81.0, "centres_sante": 121,
                "taux_scolarisation_pct": 95.8, "production_cerealiere_tonnes": 51000,
            })
            path = handle.name

        try:
            call_command("importer_statistiques", path)
            created = StatistiqueRegionale.objects.filter(region="Dakar", annee=2024).count()
            self.assertEqual(created, 1)
            record = StatistiqueRegionale.objects.get(region="Dakar", annee=2024)
            self.assertEqual(record.population, 4100000)
        finally:
            os.remove(path)

    def test_import_excel_file(self):
        from openpyxl import Workbook

        workbook = Workbook()
        sheet = workbook.active
        sheet.append([
            "region", "annee", "population", "taux_urbanisation_pct",
            "taux_alphabetisation_pct", "taux_chomage_pct", "taux_pauvrete_pct",
            "acces_internet_pct", "centres_sante", "taux_scolarisation_pct",
            "production_cerealiere_tonnes"
        ])
        sheet.append([
            "Dakar", 2024, 4200000, 86.2, 91.0, 10.4, 8.0,
            82.0, 122, 96.0, 52000,
        ])

        fd, path = tempfile.mkstemp(suffix=".xlsx")
        os.close(fd)
        try:
            workbook.save(path)
            call_command("importer_statistiques", path)
            record = StatistiqueRegionale.objects.get(region="Dakar", annee=2024)
            self.assertEqual(record.population, 4200000)
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_unique_constraint_on_region_and_year(self):
        StatistiqueRegionale.objects.create(
            region="Thiès", annee=2023, population=1000000,
            taux_urbanisation_pct=Decimal("70.0"), taux_alphabetisation_pct=Decimal("78.0"),
            taux_chomage_pct=Decimal("12.0"), taux_pauvrete_pct=Decimal("15.0"),
            acces_internet_pct=Decimal("55.0"), centres_sante=40,
            taux_scolarisation_pct=Decimal("85.0"), production_cerealiere_tonnes=15000,
        )
        with self.assertRaises(Exception):
            StatistiqueRegionale.objects.create(
                region="Thiès", annee=2023, population=1000001,
                taux_urbanisation_pct=Decimal("70.0"), taux_alphabetisation_pct=Decimal("78.0"),
                taux_chomage_pct=Decimal("12.0"), taux_pauvrete_pct=Decimal("15.0"),
                acces_internet_pct=Decimal("55.0"), centres_sante=41,
                taux_scolarisation_pct=Decimal("85.0"), production_cerealiere_tonnes=15001,
            )


class QuestionParsingTests(TestCase):
    def test_indicator_aliases_and_year_extraction(self):
        intent = extract_intent("Quelle est la population de Thiès en 2024 ?")
        self.assertEqual(intent["indicator"], "population")
        self.assertEqual(intent["operation"], "value")
        self.assertEqual(intent["years"], [2024])

    def test_sparse_question_defaults_to_population_and_latest_year(self):
        intent = extract_intent("Donne-moi la population de Dakar")
        self.assertEqual(intent["indicator"], "population")
        self.assertFalse(intent["needs_clarification"])
        self.assertEqual(intent["years"], [2024])

    def test_ambiguous_question_needs_clarification(self):
        intent = extract_intent("Donne-moi le taux de Dakar.")
        self.assertTrue(intent["needs_clarification"])


class QueryEngineTests(TestCase):
    def test_value_query_without_year_uses_latest_available_year(self):
        StatistiqueRegionale.objects.create(
            region="Dakar", annee=2023, population=3500000,
            taux_urbanisation_pct=Decimal("73.0"), taux_alphabetisation_pct=Decimal("80.0"),
            taux_chomage_pct=Decimal("14.0"), taux_pauvrete_pct=Decimal("16.0"),
            acces_internet_pct=Decimal("58.0"), centres_sante=70,
            taux_scolarisation_pct=Decimal("84.0"), production_cerealiere_tonnes=65000,
        )
        intent = extract_intent("Quelle est la population de Dakar ?")
        result = execute_intent(intent)
        self.assertEqual(result["metadata"]["rows_used"], 1)
        self.assertEqual(result["table"][0]["annee"], 2024)

    def test_dashboard_metrics_count_regions_and_years(self):
        metrics = get_dashboard_metrics()
        self.assertEqual(metrics["regions_count"], 4)
        self.assertEqual(metrics["years_count"], 2)
        self.assertEqual(metrics["indicators_count"], 9)

    @classmethod
    def setUpTestData(cls):
        StatistiqueRegionale.objects.bulk_create([
            StatistiqueRegionale(
                region="Dakar", annee=2024, population=5000000,
                taux_urbanisation_pct=Decimal("88.0"), taux_alphabetisation_pct=Decimal("95.0"),
                taux_chomage_pct=Decimal("10.0"), taux_pauvrete_pct=Decimal("8.0"),
                acces_internet_pct=Decimal("80.0"), centres_sante=150,
                taux_scolarisation_pct=Decimal("97.0"), production_cerealiere_tonnes=80000,
            ),
            StatistiqueRegionale(
                region="Thiès", annee=2024, population=2000000,
                taux_urbanisation_pct=Decimal("72.0"), taux_alphabetisation_pct=Decimal("84.0"),
                taux_chomage_pct=Decimal("14.0"), taux_pauvrete_pct=Decimal("16.0"),
                acces_internet_pct=Decimal("58.0"), centres_sante=60,
                taux_scolarisation_pct=Decimal("88.0"), production_cerealiere_tonnes=60000,
            ),
            StatistiqueRegionale(
                region="Saint-Louis", annee=2024, population=1500000,
                taux_urbanisation_pct=Decimal("69.0"), taux_alphabetisation_pct=Decimal("82.0"),
                taux_chomage_pct=Decimal("13.0"), taux_pauvrete_pct=Decimal("14.0"),
                acces_internet_pct=Decimal("60.0"), centres_sante=55,
                taux_scolarisation_pct=Decimal("87.0"), production_cerealiere_tonnes=57000,
            ),
            StatistiqueRegionale(
                region="Kaolack", annee=2020, population=1200000,
                taux_urbanisation_pct=Decimal("60.0"), taux_alphabetisation_pct=Decimal("75.0"),
                taux_chomage_pct=Decimal("22.0"), taux_pauvrete_pct=Decimal("20.0"),
                acces_internet_pct=Decimal("41.0"), centres_sante=40,
                taux_scolarisation_pct=Decimal("80.0"), production_cerealiere_tonnes=50000,
            ),
            StatistiqueRegionale(
                region="Kaolack", annee=2024, population=1300000,
                taux_urbanisation_pct=Decimal("63.0"), taux_alphabetisation_pct=Decimal("79.0"),
                taux_chomage_pct=Decimal("18.0"), taux_pauvrete_pct=Decimal("17.0"),
                acces_internet_pct=Decimal("57.8"), centres_sante=45,
                taux_scolarisation_pct=Decimal("83.0"), production_cerealiere_tonnes=55000,
            ),
        ])

    def test_value_operation_returns_single_record(self):
        intent = extract_intent("Quelle est la population de Thiès en 2024 ?")
        result = execute_intent(intent)
        self.assertEqual(result["metadata"]["rows_used"], 1)
        self.assertIn("Thiès", result["answer"])

    def test_compare_operation_returns_bars(self):
        intent = extract_intent("Compare le chômage à Dakar, Thiès et Saint-Louis en 2024.")
        result = execute_intent(intent)
        self.assertEqual(result["chart"]["type"], "bar")
        self.assertEqual(len(result["table"]), 3)

    def test_trend_operation_returns_line_chart(self):
        intent = extract_intent("Montre l’évolution de l’accès à Internet à Kaolack entre 2020 et 2024.")
        result = execute_intent(intent)
        self.assertEqual(result["chart"]["type"], "line")
        self.assertEqual(len(result["table"]), 2)

    def test_ranking_and_sum_operations(self):
        ranking_intent = extract_intent("Quelles sont les cinq régions les plus peuplées en 2024 ?")
        ranking_result = execute_intent(ranking_intent)
        self.assertEqual(ranking_result["chart"]["type"], "bar")
        self.assertLessEqual(len(ranking_result["table"]), 5)

        sum_intent = extract_intent("Quelle est la population totale estimée du Sénégal en 2024 ?")
        sum_result = execute_intent(sum_intent)
        self.assertIn("population totale", sum_result["answer"].lower())
        self.assertEqual(sum_result["metadata"]["rows_used"], 3)
