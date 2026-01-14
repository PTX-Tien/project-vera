import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add src to path so we can import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from rag_engine import process_document, lookup_document

class TestRAGEngine(unittest.TestCase):
    
    @patch('rag_engine.PyPDFLoader')
    def test_rag_retrieval(self, MockLoader):
        print("\n🧪 Testing RAG Engine Logic...")
        
        # 1. SETUP: Mock a Fake PDF
        # We simulate a PDF with specific content to see if Vera can find it.
        mock_doc = MagicMock()
        mock_doc.page_content = "Candidate Name: Tien. Skills: Python, Docker, MLOps."
        mock_doc.metadata = {"source": "dummy.pdf"}
        
        # Configure the loader to return our fake doc
        mock_loader_instance = MockLoader.return_value
        mock_loader_instance.load.return_value = [mock_doc]
        
        # 2. ACTION: Process the "dummy" file
        print("   - Processing dummy document...")
        success = process_document("dummy.pdf")
        self.assertTrue(success)
        
        # 3. VERIFY: Query the engine
        print("   - Querying: 'What are the skills?'")
        # We invoke the tool directly to see if FAISS returns the right chunk
        answer = lookup_document.invoke("What are the skills?")
        
        print(f"   - Retrieved: {answer}")
        
        # 4. ASSERT: Did it find the skills?
        self.assertIn("Python", answer)
        self.assertIn("Docker", answer)
        print("✅ RAG Test Passed!")

if __name__ == '__main__':
    unittest.main()