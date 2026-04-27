import time
from django.core.management.base import BaseCommand
from chat.services import generate_rag_answer

class Command(BaseCommand):
    help = 'Runs accuracy and correctness tests against the RAG chatbot using known questions.'

    def handle(self, *args, **kwargs):
        # 1. Define your known test cases here
        test_cases = [
            {
                "query": "What sports markets look most interesting right now?",
                "expected_keywords": ["sport", "game", "nba", "nfl", "team", "match"],
                "expect_sources": True,
            },
            {
                "query": "Who is currently favored to win the upcoming election?",
                "expected_keywords": ["election", "politics", "president", "democrat", "republican"],
                "expect_sources": True,
            },
            {
                "query": "Nonsense query xyz123 that has no data",
                "expected_keywords": ["could not find", "no relevant information"],
                "expect_sources": False, # We expect the system to fail gracefully
            }
        ]

        self.stdout.write(self.style.NOTICE(f"Starting evaluation of {len(test_cases)} known questions...\n"))

        passed = 0
        total_latency = 0

        # 2. Run the tests
        for i, case in enumerate(test_cases, 1):
            query = case["query"]
            expected_keywords = case["expected_keywords"]
            expect_sources = case["expect_sources"]

            self.stdout.write(f"Test {i}/{len(test_cases)}: '{query}'")

            start_time = time.time()
            try:
                result = generate_rag_answer(query)
                latency = time.time() - start_time
                total_latency += latency

                answer = result.get("answer", "").lower()
                sources = result.get("sources", [])

                # Evaluation Logic
                keyword_match = any(word in answer for word in expected_keywords)
                sources_match = (len(sources) > 0) == expect_sources

                if keyword_match and sources_match:
                    passed += 1
                    self.stdout.write(self.style.SUCCESS(f"  [PASS] {latency:.2f}s | Retrieved {len(sources)} sources"))
                else:
                    self.stdout.write(self.style.ERROR(f"  [FAIL] {latency:.2f}s"))
                    if not keyword_match:
                        self.stdout.write(self.style.WARNING(f"    -> Missing expected keywords. Answer snippet: {answer[:60]}..."))
                    if not sources_match:
                        self.stdout.write(self.style.WARNING(f"    -> Source mismatch. Expected sources: {expect_sources}, Got: {len(sources)}"))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  [CRASH] {str(e)}"))

        # 3. Print the Summary Report
        self.stdout.write("\n" + "="*40)
        self.stdout.write(self.style.SUCCESS("EVALUATION COMPLETE") if passed == len(test_cases) else self.style.WARNING("EVALUATION COMPLETE WITH FAILURES"))
        self.stdout.write(f"Passed: {passed}/{len(test_cases)}")
        self.stdout.write(f"Average Latency: {(total_latency / len(test_cases)):.2f}s")
        self.stdout.write("="*40 + "\n")
