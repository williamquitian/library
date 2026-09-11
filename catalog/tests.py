from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .forms import BookDatalistForm
from .models import Author, Book, Publisher


class AutocompletePageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_superuser("staff", "staff@example.com", "pw")
        cls.author = Author.objects.create(name="Ursula K. Le Guin", country="USA")
        Author.objects.create(name="Italo Calvino", country="Italy")
        cls.publisher = Publisher.objects.create(name="Penguin")

    def setUp(self):
        self.client.force_login(self.staff)

    def test_page_renders_builtin_autocomplete_widget(self):
        response = self.client.get(reverse("catalog:book_create_dropdown"))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('data-ajax--url="/admin/autocomplete/"', html)
        self.assertIn("admin/js/autocomplete.js", html)
        self.assertIn("select2", html)

    def test_admin_autocomplete_endpoint_filters_by_search_fields(self):
        response = self.client.get(
            reverse("admin:autocomplete"),
            {
                "term": "guin",
                "app_label": "catalog",
                "model_name": "book",
                "field_name": "author",
            },
        )
        self.assertEqual(response.status_code, 200)
        results = response.json()["results"]
        self.assertEqual([r["text"] for r in results], ["Ursula K. Le Guin"])

    def test_page_creates_book(self):
        response = self.client.post(
            reverse("catalog:book_create"),
            {
                "title": "The Dispossessed",
                "author": self.author.pk,
                "publisher": self.publisher.pk,
                "published": "1974-01-01",
            },
        )
        self.assertRedirects(response, reverse("catalog:book_create"))
        self.assertEqual(Book.objects.get().title, "The Dispossessed")

    def test_page_requires_staff(self):
        self.client.logout()
        response = self.client.get(reverse("catalog:book_create"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])

    def test_admin_add_form_uses_the_inline_autocomplete(self):
        response = self.client.get(reverse("admin:catalog_book_add"))
        html = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn("inline-autocomplete", html)
        self.assertIn("catalog/js/inline_autocomplete.js", html)

    def test_admin_saves_a_single_foreign_key(self):
        publisher = Publisher.objects.create(name="Vintage")
        response = self.client.post(
            reverse("admin:catalog_book_add"),
            {
                "title": "The Left Hand of Darkness",
                "author": self.author.pk,
                "publisher": publisher.pk,
                "published": "1969-01-01",
                "_save": "Save",
            },
        )
        self.assertEqual(response.status_code, 302)
        book = Book.objects.get(title="The Left Hand of Darkness")
        self.assertEqual((book.author, book.publisher), (self.author, publisher))

    def test_admin_change_form_shows_the_current_value(self):
        book = Book.objects.create(title="The Dispossessed", author=self.author)
        response = self.client.get(reverse("admin:catalog_book_change", args=[book.pk]))
        self.assertContains(response, "Ursula K. Le Guin")


class InlineSearchPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_superuser("staff2", "s2@example.com", "pw")
        cls.author = Author.objects.create(name="Toni Morrison", country="USA")

    def setUp(self):
        self.client.force_login(self.staff)

    def test_widget_renders_a_multiple_select_with_its_own_init(self):
        response = self.client.get(reverse("catalog:book_create"))
        html = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn("inline-autocomplete", html)
        self.assertIn("multiple", html)
        self.assertIn("catalog/js/inline_autocomplete.js", html)
        self.assertIn('data-ajax--url="/admin/autocomplete/"', html)

    def test_single_value_still_posts_as_a_foreign_key(self):
        response = self.client.post(
            reverse("catalog:book_create"),
            {"title": "Beloved", "author": self.author.pk, "publisher": "", "published": ""},
        )
        self.assertRedirects(response, reverse("catalog:book_create"))
        self.assertEqual(Book.objects.get().author, self.author)


class DatalistPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = Author.objects.create(name="Octavia E. Butler", country="USA")
        Author.objects.create(name="Isabel Allende", country="Chile")

    def test_page_is_public_and_renders_a_datalist(self):
        response = self.client.get(reverse("catalog:book_create_datalist"))
        html = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn("<datalist", html)
        self.assertIn('list="id_author__list"', html)
        self.assertNotIn("select2.full", html)  # no JS library involved

    def test_search_endpoint(self):
        response = self.client.get(reverse("catalog:model_search", args=["author"]), {"q": "butl"})
        self.assertEqual(
            [r["text"] for r in response.json()["results"]], ["Octavia E. Butler"]
        )
        self.assertEqual(
            self.client.get(reverse("catalog:model_search", args=["user"])).status_code, 404
        )

    def test_typed_name_resolves_to_the_instance(self):
        response = self.client.post(
            reverse("catalog:book_create_datalist"),
            {"title": "Kindred", "author": "octavia e. butler", "publisher": "", "published": ""},
        )
        self.assertRedirects(response, reverse("catalog:book_create_datalist"))
        self.assertEqual(Book.objects.get().author, self.author)

    def test_unknown_name_is_a_validation_error(self):
        response = self.client.post(
            reverse("catalog:book_create_datalist"),
            {"title": "Nope", "author": "Nobody At All", "publisher": "", "published": ""},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context["form"], "author", "“Nobody At All” is not in the list. Pick one of the suggestions."
        )
        self.assertFalse(Book.objects.exists())

    def test_existing_book_redisplays_the_label(self):
        book = Book.objects.create(title="Kindred", author=self.author)
        form = BookDatalistForm(instance=book)
        self.assertEqual(form["author"].value(), "Octavia E. Butler")
