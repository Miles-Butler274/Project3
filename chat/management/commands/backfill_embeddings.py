from django.core.management.base import BaseCommand

from markets.models import Market, SourceDocument
from chat.embeddings import embed_text


class Command(BaseCommand):
    help = "Backfill embeddings for existing markets and source documents"

    def handle(self, *args, **options):
        for market in Market.objects.all():
            market.embedding = embed_text(
                f"{market.question}\n{market.description}\n{market.category}"
            )
            market.save(update_fields=["embedding"])
        self.stdout.write(self.style.SUCCESS("Updated market embeddings"))

        for doc in SourceDocument.objects.all():
            doc.embedding = embed_text(f"{doc.title}\n{doc.cleaned_text}")
            doc.save(update_fields=["embedding"])
        self.stdout.write(self.style.SUCCESS("Updated document embeddings"))
