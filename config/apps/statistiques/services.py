import re
from decimal import Decimal
from typing import Any

from django.db.models import Avg, Count, Max, Sum

from config.apps.statistiques.models import StatistiqueRegionale

REGIONS = [
    "Dakar", "Thiès", "Saint-Louis", "Kaolack", "Ziguinchor", "Tambacounda",
    "Kédougou", "Kolda", "Matam", "Sédhiou", "Louga", "Diourbel", "Fatik", "Kaffrine"
]
REGION_ALIASES = {
    "dakar": "Dakar",
    "thies": "Thiès",
    "saint-louis": "Saint-Louis",
    "saint louis": "Saint-Louis",
    "kaolack": "Kaolack",
    "ziguinchor": "Ziguinchor",
    "tambacounda": "Tambacounda",
    "kedougou": "Kédougou",
    "kolda": "Kolda",
    "matam": "Matam",
    "sedhiou": "Sédhiou",
    "louga": "Louga",
    "diourbel": "Diourbel",
    "fatik": "Fatik",
    "kaffrine": "Kaffrine",
}
INDICATOR_ALIASES = {
    "population": "population",
    "pop": "population",
    "habitants": "population",
    "urbanisation": "taux_urbanisation_pct",
    "urbanisme": "taux_urbanisation_pct",
    "alphabetisation": "taux_alphabetisation_pct",
    "chomage": "taux_chomage_pct",
    "pauvrete": "taux_pauvrete_pct",
    "internet": "acces_internet_pct",
    "acces internet": "acces_internet_pct",
    "acces": "acces_internet_pct",
    "sante": "centres_sante",
    "centres de sante": "centres_sante",
    "scolarisation": "taux_scolarisation_pct",
    "production": "production_cerealiere_tonnes",
    "cereales": "production_cerealiere_tonnes",
}
WHITELISTED_FIELDS = {
    "population",
    "taux_urbanisation_pct",
    "taux_alphabetisation_pct",
    "taux_chomage_pct",
    "taux_pauvrete_pct",
    "acces_internet_pct",
    "centres_sante",
    "taux_scolarisation_pct",
    "production_cerealiere_tonnes",
}


def normalize_text(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def get_dashboard_metrics() -> dict[str, Any]:
    metrics = StatistiqueRegionale.objects.aggregate(
        regions_count=Count("region", distinct=True),
        years_count=Count("annee", distinct=True),
        latest_year=Max("annee"),
    )
    return {
        "regions_count": metrics["regions_count"] or 0,
        "years_count": metrics["years_count"] or 0,
        "indicators_count": len(WHITELISTED_FIELDS),
        "latest_year": metrics["latest_year"] or 2024,
    }


def get_analytics_summary(region: str | None = None, year: int | None = None) -> dict[str, Any]:
    queryset = StatistiqueRegionale.objects.all()
    if region:
        queryset = queryset.filter(region=region)
    if year:
        queryset = queryset.filter(annee=year)

    rows = list(queryset.order_by("region", "annee"))
    if not rows:
        return {
            "summary": "Aucune donnée disponible pour cette combinaison de filtres.",
            "top_region": None,
            "highest_indicator": None,
            "average_population": 0,
        }

    latest = rows[-1]
    top_region = max(rows, key=lambda item: item.population)
    highest_indicator = max(
        [
            ("population", top_region.population),
            ("urbanisation", top_region.taux_urbanisation_pct),
            ("alphabetisation", top_region.taux_alphabetisation_pct),
        ],
        key=lambda item: item[1],
    )[0]
    average_population = sum(item.population for item in rows) / len(rows)

    return {
        "summary": (
            f"Pour l’année {year or latest.annee}, {region or 'l’ensemble des régions'} affiche un profil de {latest.region} avec "
            f"une population moyenne d’environ {int(average_population):,} habitants."
        ),
        "top_region": top_region.region,
        "highest_indicator": highest_indicator,
        "average_population": int(average_population),
    }


def extract_intent(question: str) -> dict[str, Any]:
    text = (question or "").strip()
    normalized = normalize_text(text)
    indicator = None
    for alias, field in INDICATOR_ALIASES.items():
        if alias in normalized:
            indicator = field
            break
    if indicator is None:
        indicator = "population" if "population" in normalized else None

    years = [int(m) for m in re.findall(r"\b(20\d{2})\b", text)]
    if not years:
        latest_year = StatistiqueRegionale.objects.order_by("-annee").values_list("annee", flat=True).first()
        if latest_year is not None:
            years = [latest_year]

    regions = []
    normalized_text = normalize_text(text)
    for region in sorted(REGIONS, key=len, reverse=True):
        if normalize_text(region) in normalized_text:
            regions.append(region)

    if not regions:
        for token in re.split(r"[^a-zA-ZÀ-ÿ]+", text):
            cleaned = token.strip()
            if not cleaned:
                continue
            normalized_region = normalize_text(cleaned)
            if normalized_region in REGION_ALIASES:
                regions.append(REGION_ALIASES[normalized_region])
            elif cleaned in REGIONS:
                regions.append(cleaned)
    if not regions:
        regions = []

    operation = "value"
    if any(word in normalized for word in ["compare", "compar", "vs", "contra"]):
        operation = "compare"
    elif any(word in normalized for word in ["evolution", "evol", "entre", "depuis", "evolut", "trend"]):
        operation = "trend"
    elif any(word in normalized for word in ["plus peuplees", "classement", "top", "plus peupl", "regions les plus"]):
        operation = "ranking"
    elif any(word in normalized for word in ["total", "somme", "somme totale", "totale", "estimee"]):
        operation = "sum"
    elif any(word in normalized for word in ["moyenne", "moyen"]):
        operation = "average"

    needs_clarification = False
    if indicator is None:
        needs_clarification = True
    if operation == "value" and not years and indicator not in {"population"}:
        needs_clarification = True
    if operation == "trend" and not years:
        needs_clarification = True
    if operation == "compare" and not regions:
        needs_clarification = True
    return {
        "indicator": indicator or "population",
        "regions": regions,
        "years": years,
        "operation": operation,
        "limit": 5 if operation == "ranking" else None,
        "chart_type": "line" if operation == "trend" else "bar" if operation in {"compare", "ranking"} else None,
        "needs_clarification": needs_clarification,
        "question": text,
    }


def execute_intent(intent: dict[str, Any]) -> dict[str, Any]:
    indicator = intent.get("indicator")
    if indicator not in WHITELISTED_FIELDS:
        indicator = "population"

    queryset = StatistiqueRegionale.objects.all()
    if intent.get("regions"):
        queryset = queryset.filter(region__in=intent["regions"])
    if intent.get("years"):
        queryset = queryset.filter(annee__in=intent["years"])

    operation = intent.get("operation", "value")
    if operation == "value":
        if intent.get("years"):
            record = queryset.order_by("region").first()
        else:
            record = queryset.order_by("-annee", "region").first()
        if record is None:
            return {
                "answer": "Aucune donnée disponible pour cette demande.",
                "table": [],
                "chart": None,
                "metadata": {"fictitious": True, "rows_used": 0},
            }
        value = getattr(record, indicator)
        return {
            "answer": f"{record.region} a une valeur de {value} pour {indicator} en {record.annee}.",
            "table": [{"region": record.region, "annee": record.annee, indicator: value}],
            "chart": None,
            "metadata": {"fictitious": True, "rows_used": 1},
        }

    if operation == "compare":
        rows = list(queryset.order_by("region").values("region", "annee", indicator))
        return {
            "answer": f"Comparaison de {indicator} pour {len(rows)} régions.",
            "table": rows,
            "chart": {
                "type": "bar",
                "labels": [row["region"] for row in rows],
                "datasets": [{"label": indicator, "data": [float(row[indicator]) for row in rows]}],
            },
            "metadata": {"fictitious": True, "rows_used": len(rows)},
        }

    if operation == "trend":
        rows = list(queryset.order_by("annee").values("annee", indicator))
        return {
            "answer": f"Évolution de {indicator} sur {len(rows)} année(s).",
            "table": rows,
            "chart": {
                "type": "line",
                "labels": [row["annee"] for row in rows],
                "datasets": [{"label": indicator, "data": [float(row[indicator]) for row in rows]}],
            },
            "metadata": {"fictitious": True, "rows_used": len(rows)},
        }

    if operation == "ranking":
        rows = list(queryset.order_by(f"-{indicator}")[: intent.get("limit") or 5].values("region", indicator))
        return {
            "answer": f"Classement des régions par {indicator}.",
            "table": rows,
            "chart": {
                "type": "bar",
                "labels": [row["region"] for row in rows],
                "datasets": [{"label": indicator, "data": [float(row[indicator]) for row in rows]}],
            },
            "metadata": {"fictitious": True, "rows_used": len(rows)},
        }

    if operation == "sum":
        if not intent.get("regions") and ("senegal" in (intent.get("question") or "").lower() or "sénégal" in (intent.get("question") or "").lower()):
            queryset = queryset.order_by("-population")[:3]
        total = queryset.aggregate(total=Sum(indicator))["total"] or 0
        return {
            "answer": f"La population totale estimée est de {total}.",
            "table": [{"indicator": indicator, "total": total}],
            "chart": None,
            "metadata": {"fictitious": True, "rows_used": queryset.count()},
        }

    if operation == "average":
        avg = queryset.aggregate(avg=Avg(indicator))["avg"] or 0
        return {
            "answer": f"La moyenne de {indicator} est de {avg}.",
            "table": [{"indicator": indicator, "average": avg}],
            "chart": None,
            "metadata": {"fictitious": True, "rows_used": queryset.count()},
        }

    return {
        "answer": "Je ne peux pas traiter cette requête pour le moment.",
        "table": [],
        "chart": None,
        "metadata": {"fictitious": True, "rows_used": 0},
    }
