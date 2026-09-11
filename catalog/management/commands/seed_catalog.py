from django.core.management.base import BaseCommand

from catalog.models import Author, Publisher

AUTHORS = [
    ("Ursula K. Le Guin", "USA"),
    ("Gabriel García Márquez", "Colombia"),
    ("Chinua Achebe", "Nigeria"),
    ("Italo Calvino", "Italy"),
    ("Toni Morrison", "USA"),
    ("Haruki Murakami", "Japan"),
    ("Jorge Luis Borges", "Argentina"),
    ("Virginia Woolf", "UK"),
    ("Octavia E. Butler", "USA"),
    ("Isabel Allende", "Chile"),
]
PUBLISHERS = ["Penguin", "Alfaguara", "Faber & Faber", "Anagrama", "Vintage"]


class Command(BaseCommand):
    help = "Create sample authors and publishers to search with the autocomplete."

    def handle(self, *args, **options):
        for name, country in AUTHORS:
            Author.objects.get_or_create(name=name, defaults={"country": country})
        for name in PUBLISHERS:
            Publisher.objects.get_or_create(name=name)
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {Author.objects.count()} authors and {Publisher.objects.count()} publishers."
            )
        )
