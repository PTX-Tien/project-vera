import sys
import os
import logging
import time
from dotenv import load_dotenv 

# --- 1. SETUP PATHS & ENVS ---
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# FIX: Add BOTH the root folder and the 'src' folder to Python Path
# This ensures 'from budget import ...' works inside agent.py
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import from src.agent (this will now work because src is in path)
# Note: Since we added '../src' to path, we could also do 'from agent import...' 
# but keeping 'src.agent' is safer for namespacing.
from src.agent import get_vera_graph
from langchain_core.messages import HumanMessage

# Configure Logging
logging.basicConfig(level=logging.ERROR)

class VeraTester:
    def __init__(self):
        print("🚀 Initializing Vera Test Suite...")
        self.graph = get_vera_graph()
        self.results = []

    def run_test(self, test_name, prompt, should_search):
        """
        Runs a single test case with TIMING logs.
        """
        print(f"\n⏱️  Testing: {test_name}...")
        start_time = time.time()
        
        try:
            inputs = {"messages": [HumanMessage(content=prompt)]}
            
            # Trace variables
            tool_called = False
            
            # Run the Agent Stream
            for event in self.graph.stream(inputs):
                step_time = time.time()
                elapsed = step_time - start_time
                
                for node, value in event.items():
                    print(f"   ↳ [+{elapsed:.2f}s] Node '{node}' finished.")
                    
                    if node == "tools":
                        tool_called = True
                        # Debug: How much data did we fetch?
                        tool_msg = value["messages"][0]
                        content_len = len(str(tool_msg.content))
                        print(f"      ⚠️ Tool fetched {content_len} chars of text")

            total_time = time.time() - start_time
            print(f"   🏁 Total Time: {total_time:.2f}s")
            
            # Evaluate
            search_behavior_correct = (tool_called == should_search)
            
            if search_behavior_correct:
                print("   ✅ PASS")
                self.results.append((test_name, "PASS"))
            else:
                print(f"   ❌ FAIL (Expected Search: {should_search}, Got: {tool_called})")
                self.results.append((test_name, "FAIL"))

        except Exception as e:
            print(f"   ⚠️ ERROR: {e}")
            self.results.append((test_name, "ERROR"))

    def print_summary(self):
        print("\n" + "="*30)
        print("       TEST SUMMARY       ")
        print("="*30)
        passed = sum(1 for _, status in self.results if status == "PASS")
        total = len(self.results)
        
        for name, status in self.results:
            icon = "✅" if status == "PASS" else "❌"
            print(f"{icon} {name}")
            
        print("-"*30)
        print(f"Result: {passed}/{total} Passed")
        
        if passed == total:
            print("🎉 READY FOR DEPLOYMENT")
        else:
            print("🔥 FIX BUGS BEFORE COMMIT")

# --- EXECUTION ---
if __name__ == "__main__":
    tester = VeraTester()
    
    # 1. Identity (Should be fast & No Search)
    tester.run_test("Identity Check", "Who are you?", should_search=False)
    
    # 2. Knowledge (Should search)
    tester.run_test("CES 2026 Knowledge", "What did Jensen Huang say about robots at CES 2026?", should_search=True)
    
    # 3. Math (Should be fast & No Search)
    tester.run_test("General Knowledge", "What is 2 + 2? Answer directly without searching.", should_search=False)
    
    # 4. Safety (Should be fast & No Search)
    tester.run_test("Gibberish Input", "asdf jkl;", should_search=False)

    tester.print_summary()