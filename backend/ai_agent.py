import os
import json
from datetime import datetime
import logging
import openai
import requests
from firebase_admin import firestore
from langchain_core.messages import SystemMessage
from livekit import api
# from livekit.api import Room
import firebase_admin
from firebase_admin import credentials
from livekit.protocol.room import CreateRoomRequest
from langchain_openai import ChatOpenAI
from langchain_together import ChatTogether
from dotenv import load_dotenv
import asyncio

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Firebase
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")
LIVEKIT_URL = os.getenv("LIVEKIT_URL")
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")

llm = ChatTogether(
    model="meta-llama/Llama-3.3-70B-Instruct-Turbo-Free",
    together_api_key=TOGETHER_API_KEY
)

class AIAgent:
    def __init__(self):
        """Initialize the AI Agent with salon information"""
        self.salon_info = self._load_salon_info()
        logger.info("AI Agent initialized")

    def create_ai_prompt(self, customer_question):
        """Create a prompt for the AI with salon information and knowledge base context"""
        salon_info_str = json.dumps(self.salon_info, indent=2)
        kb_context = self._get_knowledge_base_context()
        
        prompt = f"""You are an AI receptionist for {self.salon_info['name']}.
                Use the salon information and knowledge base below to answer customer questions.
                If you don't know the answer or are uncertain, respond with "I_NEED_HELP" followed by the question.
                
                SALON INFORMATION:
                {salon_info_str}
                
                KNOWLEDGE BASE:
                {kb_context}
                
                CUSTOMER QUESTION:
                {customer_question}
                
                YOUR RESPONSE:
                """
        
        return prompt

    async def process_call(self, customer_phone, customer_question):
        """Process a customer call with a question"""
        logger.info(f"Processing call from {customer_phone}: {customer_question}")
        
        # Create AI prompt
        logger.info("Creating Livekit Room")
        await self.create_livekit_room(customer_phone)
        logger.info("Created Livekit Room Successfully")
        prompt = self.create_ai_prompt(customer_question)
        
        try:
            # Get AI response (using OpenAI)
            messages = [SystemMessage(content=prompt)]
            answer = llm.invoke(messages).content

            # Check if AI needs help
            if answer.startswith("I_NEED_HELP"):
                logger.info("AI needs help, escalating to supervisor")
                return self.escalate_to_supervisor(customer_phone, customer_question)
            else:
                logger.info(f"AI answered: {answer}")
                return {"status": "answered", "response": answer}
                
        except Exception as e:
            logger.error(f"Error processing call: {e}")
            return {"status": "error", "response": str(e)}

    async def create_livekit_room(self, customer_phone):
        """Create a LiveKit room for a call"""
        try:
            room_name = f"call_{customer_phone}_{int(datetime.now().timestamp())}"
            await api.LiveKitAPI().room.create_room(CreateRoomRequest(
                name=room_name,
                empty_timeout=10 * 60,
                max_participants=20,
            ))
            return room_name
        except Exception as e:
            logger.error(f"Error creating LiveKit room: {e}")
            return None

    def _load_salon_info(self):
        """Load salon information from JSON file"""
        try:
            with open("salon_info.json", "r") as file:
                return json.load(file)
        except FileNotFoundError:
            logger.error("Salon information file not found")
            return

    def _get_knowledge_base_context(self):
        """Retrieve relevant information from knowledge base"""
        # Query the knowledge base for all entries
        # In a production system, this would be optimized to retrieve only relevant entries
        kb_ref = db.collection('knowledge_base')
        kb_docs = kb_ref.stream()

        kb_context = []
        for doc in kb_docs:
            kb_data = doc.to_dict()
            kb_context.append(f"Q: {kb_data['question']}\nA: {kb_data['answer']}")

        return "\n\n".join(kb_context)

    def _notify_supervisor(self, request_id, question):
        """Simulate sending notification to supervisor"""
        notification_message = f"Hey, I need help answering: {question}"
        logger.info(f"SUPERVISOR NOTIFICATION: {notification_message}")
        logger.info(f"Request ID: {request_id}")

        # In a real implementation, this would send a text or trigger a webhook
        # Example webhook call (commented out):
        requests.post(
            os.getenv("SUPERVISOR_WEBHOOK_URL"),
            json={"request_id": request_id, "message": notification_message}
        )

    def _update_knowledge_base(self, question, answer, request_id):
        """Update the knowledge base with new information"""
        # Check if similar question already exists (simplified implementation)
        # In production, you'd use semantic search or better matching

        kb_item = {
            "question": question,
            "answer": answer,
            "createdAt": datetime.now(),
            "lastUsedAt": datetime.now(),
            "useCount": 1,
            "originatingRequestId": request_id
        }

        # Add to knowledge base
        db.collection('knowledge_base').add(kb_item)
        logger.info(f"Knowledge base updated with new Q&A: {question}")

    def escalate_to_supervisor(self, customer_phone, customer_question):
        """Escalate the question to a human supervisor"""
        logger.info(f"Creating help request for customer {customer_phone}")

        # Create help request in database
        help_request = {
            "customerPhone": customer_phone,
            "question": customer_question,
            "timestamp": datetime.now(),
            "status": "pending",
            "responseText": None,
            "respondedAt": None,
            "followupSent": False,
            "followupTimestamp": None
        }

        # Add to Firestore
        request_ref = db.collection('help_requests').document()
        request_ref.set(help_request)
        request_id = request_ref.id

        # Simulate notifying supervisor (in production, this could be a text or app notification)
        self._notify_supervisor(request_id, customer_question)

        return {
            "status": "escalated",
            "request_id": request_id,
            "message": "Let me check with my supervisor and get back to you."
        }

    def follow_up_with_customer(self, request_id, response_text):
        """Follow up with customer after receiving supervisor response"""
        # Get request data
        request_ref = db.collection('help_requests').document(request_id)
        request_data = request_ref.get().to_dict()

        if not request_data:
            logger.error(f"Request {request_id} not found")
            return False

        customer_phone = request_data["customerPhone"]
        question = request_data["question"]

        # Simulate sending follow-up message to customer
        logger.info(f"SENDING FOLLOW-UP to {customer_phone}: {response_text}")

        # Update request with follow-up info
        request_ref.update({
            "followupSent": True,
            "followupTimestamp": datetime.now()
        })

        # Update knowledge base with new information
        self._update_knowledge_base(question, response_text, request_id)

        return True


async def main():
    agent = AIAgent()
    livekit_api = api.LiveKitAPI(
        url=LIVEKIT_URL,
        api_key=LIVEKIT_API_KEY,
        api_secret=LIVEKIT_API_SECRET
    )

    try:
        result1 = await agent.process_call("+6281237154", "How was pricing established?")
        print(result1)
        result2 = await agent.process_call("+9848265838", "Do you have any specials for repeat customers?")
        print(result2)
    finally:
        await livekit_api.aclose()

if __name__ == "__main__":
    asyncio.run(main())


    # Run the