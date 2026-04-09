from django.core.management.base import BaseCommand

from ingestion.utils import split_text_into_chunks
from markets.embeddings import embed_text
from markets.models import DocumentChunk, Market, SourceDocument


class Command(BaseCommand):
    help = "Backfill embeddings for markets, documents, and document chunks"

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

            doc.chunks.all().delete()
            chunks = split_text_into_chunks(doc.cleaned_text or doc.raw_text)

            chunk_objects = []
            for idx, chunk_text in enumerate(chunks):
                chunk_objects.append(
                    DocumentChunk(
                        document=doc,
                        chunk_index=idx,
                        text=chunk_text,
                        embedding=embed_text(f"{doc.title}\n{chunk_text}"),
                    )
                )

            if chunk_objects:
                DocumentChunk.objects.bulk_create(chunk_objects)

        self.stdout.write(self.style.SUCCESS("Updated document and chunk embeddings"))
