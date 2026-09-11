from django.db import models


class Author(models.Model):
    name = models.CharField(max_length=120)
    country = models.CharField(max_length=60, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Publisher(models.Model):
    name = models.CharField(max_length=120)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Book(models.Model):
    title = models.CharField(max_length=200)
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name="books")
    publisher = models.ForeignKey(
        Publisher, on_delete=models.SET_NULL, null=True, blank=True, related_name="books"
    )
    published = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title
