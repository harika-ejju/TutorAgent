import os
import json
import uuid
import time
import re
import redis.asyncio as redis
import requests
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")  # Default fallback

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for deployment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check endpoint
@app.get("/")
@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "Tutor Agent API is running"}

@app.on_event("startup")
async def startup_event():
    print("Starting up Tutor Agent API...")
    print(f"OpenAI API Key configured: {'Yes' if OPENAI_API_KEY else 'No'}")
    print(f"Redis URL: {REDIS_URL}")

class UserLogin(BaseModel):
    email: str
    password: str

class UserCreate(BaseModel):
    username: str
    email: str
    password: str


class ConnectionManager:
    def __init__(self):
        self.connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.connections[user_id] = websocket

    def disconnect(self, user_id: str):
        self.connections.pop(user_id, None)

    async def send(self, user_id: str, message: dict):
        websocket = self.connections.get(user_id)
        if websocket:
            await websocket.send_json(message)

manager = ConnectionManager()

async def call_openai(prompt: str) -> str:
    import asyncio
    
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-3.5-turbo",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 2000  
    }
    
    # Using requests instead of httpx for better deployment compatibility
    response = await asyncio.to_thread(requests.post, 
                                     "https://api.openai.com/v1/chat/completions",
                                     headers=headers, 
                                     json=payload,
                                     timeout=30)
    
    if response.status_code == 200:
        data = response.json()
        return data["choices"][0]["message"]["content"]
    else:
        print(f"OpenAI API Error: {response.status_code} - {response.text}")
        return "Sorry, I couldn't generate a response at the moment."

async def handle_message(user_id: str, msg: dict, manager: ConnectionManager):
    print(f"Handling message for {user_id}: {msg}")
    
    # Make Redis connection optional for deployment
    rdb = None
    try:
        rdb = redis.from_url(REDIS_URL, decode_responses=True)
        await rdb.ping()  # Test connection
    except Exception as e:
        print(f"Redis connection failed: {e}. Continuing without Redis.")
        rdb = None


    if msg["type"] in ["start_lesson", "chat_message", "message"]:
        topic = msg.get("topic") or msg.get("message") or msg.get("content")
        
        # Only store non-casual conversations
        casual_words = ["hi", "hello", "hey", "thanks", "thank you", "bye", "goodbye", "ok", "okay"]
        if not (any(word in topic.lower().strip() for word in casual_words) and len(topic.split()) <= 3):
            conversation_id = str(uuid.uuid4())
            conversation = {
                "id": conversation_id,
                "title": topic[:50] + "..." if len(topic) > 50 else topic,
                "topic": topic,
                "timestamp": str(int(time.time())),
                "user_id": user_id
            }
            
            user_conversations = await rdb.get(f"user_conversations:{user_id}")
            conversations = json.loads(user_conversations) if user_conversations else []
            conversations.insert(0, conversation)
            conversations = conversations[:20] 
            await rdb.setex(f"user_conversations:{user_id}", 2592000, json.dumps(conversations))

    if (msg["type"] == "start_lesson" and msg.get("topic")) or (msg["type"] == "chat_message" and msg.get("message")) or (msg["type"] == "message" and msg.get("content")):
        raw_topic = msg.get("topic") or msg.get("message") or msg.get("content")
        print(f"Processing raw input: {raw_topic}")
    
        casual_words = ["hi", "hello", "hey", "thanks", "thank you", "bye", "goodbye", "ok", "okay"]
        if any(word in raw_topic.lower().strip() for word in casual_words) and len(raw_topic.split()) <= 3:
            
            casual_prompt = f"Respond briefly and friendly to this casual message: {raw_topic}. Keep it conversational and helpful."
            content = await call_openai(casual_prompt)
            await manager.send(user_id, {"type": "message", "content": content})
        else:
            
            await manager.send(user_id, {"type": "typing", "content": "Thinking..."})
            
            
            lesson_prompt = f"""Respond to this user request: "{raw_topic}"

If it's asking to learn about a topic, teach it in 5 clear steps:
- Basic definition and concept
- Key ideas and rules
- Process and methodology  
- 2 concrete examples
- Significance and applications

If it's a general question, provide a helpful and educational answer.
Keep responses clear and educational."""

            print(f"Calling OpenAI with prompt for: {raw_topic}")
            content = await call_openai(lesson_prompt)
            print(f"Generated content: {content[:200]}...")
            
            await manager.send(user_id, {"type": "message", "content": content})
            
            topic = raw_topic.lower()
            topic = re.sub(r'^(explain|tell|teach|show|what|how|where|when|why|can you)\s+(me\s+)?(about\s+)?', '', topic)
            topic = re.sub(r'^(is|are|does|do)\s+', '', topic)
            topic = re.sub(r'\?+$', '', topic)  
            
            topic = topic.strip()
            if len(topic.split()) > 6:
                topic = " ".join(topic.split()[:6])
            
            if not topic or len(topic) < 3:
                topic = raw_topic.strip()
                if len(topic.split()) > 4:
                    topic = " ".join(topic.split()[:4])
            
            print(f"DEBUG: Extracted topic: '{topic}' from raw input: '{raw_topic}'")
            
    
            if not any(avoid in raw_topic.lower() for avoid in ["hello", "hi", "thanks", "thank you", "bye", "goodbye", "ok", "okay"]):
                print(f"DEBUG: Sending assessment offer for topic: '{topic}'")
                await manager.send(user_id, {
                    "type": "assessment_offer",
                    "topic": topic,
                    "content": f"Would you like to take a quick test?"
                })
            else:
                print(f"DEBUG: NOT sending assessment offer - casual greeting detected")

    elif msg["type"] == "start_assessment" and msg.get("topic"):
        print(f"DEBUG: Received start_assessment request for topic: {msg.get('topic')}")
        topic = msg["topic"]
        
        topic_key = topic.replace(' ', '_').lower()
        await rdb.delete(f"assessment:{user_id}:{topic_key}")
    
        assessment_prompt = f"""Create 3 multiple choice questions about "{topic}".

Each question should test understanding of {topic}. Return JSON format:

{{
  "questions": [
    {{
      "id": "q1",
      "question": "[specific question about {topic}]",
      "options": ["[real option A]", "[real option B]", "[real option C]", "[real option D]"],
      "correct_answer": "[correct option text]"
    }},
    {{
      "id": "q2", 
      "question": "[different question about {topic}]",
      "options": ["[real option A]", "[real option B]", "[real option C]", "[real option D]"],
      "correct_answer": "[correct option text]"
    }},
    {{
      "id": "q3",
      "question": "[third question about {topic}]",
      "options": ["[real option A]", "[real option B]", "[real option C]", "[real option D]"],
      "correct_answer": "[correct option text]"
    }}
  ]
}}

Make questions specific and educational about {topic}."""

        try:
    
            print(f"Generating assessment for topic: {topic}")
            questions_response = await call_openai(assessment_prompt)
            print(f"AI Response: {questions_response[:200]}...")
            
            
            questions_json = questions_response.strip()
            if questions_json.startswith('```json'):
                questions_json = questions_json[7:-3].strip()
            elif questions_json.startswith('```'):
                questions_json = questions_json[3:-3].strip()
            
            print(f"Cleaned JSON: {questions_json[:200]}...")
            questions_data = json.loads(questions_json)
            
            if "questions" in questions_data and len(questions_data["questions"]) >= 1:
                assessment = {
                    "id": str(uuid.uuid4()),
                    "topic": topic,
                    "questions": questions_data["questions"],
                    "timestamp": str(int(time.time()))
                }
                print(f"Successfully generated AI assessment with {len(questions_data['questions'])} questions")
            else:
                print(f"AI response invalid: {questions_data}")
                raise ValueError("Invalid AI response format")
                
        except Exception as e:
            print(f"Error generating AI questions: {e}")
            print("Using fallback questions")
    
        try:
            await rdb.setex(f"assessment:{user_id}:{topic.replace(' ', '_').lower()}", 3600, json.dumps(assessment))
            await rdb.setex(f"assessment:{assessment['id']}", 3600, json.dumps(assessment))
            await manager.send(user_id, {"type": "assessment", "assessment": assessment})
        except Exception as e:
            await manager.send(user_id, {"type": "error", "content": "Failed to create assessment"})

    elif msg["type"] == "submit_assessment" and msg.get("assessment_id") and msg.get("answers"):
        assessment_id = msg["assessment_id"]
        user_answers = msg["answers"]
        
        print(f"Processing assessment submission: {assessment_id}")
        print(f"User answers: {user_answers}")
        
        try:
        
            assessment_data = await rdb.get(f"assessment:{assessment_id}")
            print(f"Assessment data found: {assessment_data is not None}")
            if not assessment_data:
                print("Assessment not found in Redis")
                await manager.send(user_id, {"type": "error", "content": "Assessment not found"})
                return
                
            assessment = json.loads(assessment_data)
            topic = assessment["topic"]
            print(f"Processing assessment for topic: {topic}")
            
            
            evaluation_prompt = f"""Evaluate this assessment about "{topic}" and provide detailed feedback with pass/fail determination.

Questions and Answers:
"""
            
            questions_for_eval = []
            for question in assessment["questions"]:
                user_answer = user_answers.get(question["id"], "No answer provided")
                questions_for_eval.append({
                    "question": question["question"],
                    "options": question["options"],
                    "correct_answer": question["correct_answer"],
                    "user_answer": user_answer,
                    "explanation": question.get("explanation", "No explanation provided")
                })
                
                evaluation_prompt += f"""\n\nQuestion: {question["question"]}
Options: {', '.join(question["options"])}
Correct Answer: {question["correct_answer"]}
User Answer: {user_answer}
"""
            
            evaluation_prompt += f"""\n\nProvide evaluation in this JSON format:
{{
  "overall_score": <percentage 0-100 EXACT calculation: correct_answers/total_questions*100>,
  "pass_status": "<pass/retake/improve>",
  "overall_feedback": "<comprehensive feedback about performance>",
  "detailed_feedback": [
    {{
      "question": "<question text>",
      "user_answer": "<user's answer>", 
      "correct_answer": "<correct answer>",
      "is_correct": <true/false - MUST be false if answers don't match exactly>,
      "explanation": "<detailed explanation of why answer is right/wrong>",
      "score": <points earned - 1 if correct, 0 if wrong>
    }}
}}

Scoring criteria:
- Below 50%: Recommend retaking the lesson with encouraging message
- 50-79%: Provide specific areas for improvement and targeted suggestions  
- 80% and above: Congratulate with enthusiastic message about mastery

Be specific and educational in your feedback. Focus on helping the user learn."""

            try:
                
                print(f"Calling OpenAI for evaluation with {len(questions_for_eval)} questions")
                eval_response = await call_openai(evaluation_prompt)
                print(f"OpenAI evaluation response received: {eval_response[:200]}...")
                
                eval_json = eval_response.strip()
                if eval_json.startswith('```json'):
                    eval_json = eval_json[7:-3].strip()
                elif eval_json.startswith('```'):
                    eval_json = eval_json[3:-3].strip()
                
                llm_result = json.loads(eval_json)
                
                final_score = actual_score  
                
                if final_score >= 80:
                    final_pass_status = "pass"
                elif final_score >= 50:
                    final_pass_status = "improve" 
                else:
                    final_pass_status = "retake"
                
        
                result = {
                    "score": final_score,
                    "pass_status": final_pass_status,
                    "correct_answers": actual_correct,
                    "total_questions": len(assessment["questions"]),
                    "feedback": llm_result.get("detailed_feedback", []),
                    "overall_feedback": llm_result.get("overall_feedback", "Assessment completed."),
                    "suggestions": llm_result.get("suggestions", ""),
                    "strengths": llm_result.get("strengths", ""),
                    "weakness_areas": llm_result.get("weakness_areas", ""),
                    "congratulatory_message": llm_result.get("congratulatory_message", ""),
                    "retake_message": llm_result.get("retake_message", ""),
                    "improvement_message": llm_result.get("improvement_message", ""),
                    "topic": topic
                }
                
            except Exception as e:
                print(f"LLM evaluation failed: {e}")

            result["timestamp"] = int(time.time())
            await rdb.setex(f"assessment_result:{user_id}:{assessment_id}", 3600, json.dumps(result))
            
            await manager.send(user_id, {"type": "assessment_result", "result": result})
            
        except Exception as e:
            print(f"Error processing assessment: {e}")
            await manager.send(user_id, {"type": "error", "content": "Failed to process assessment"})
    else:
        await manager.send(user_id, {"type": "error", "content": "Unsupported message type or missing data."})

    await rdb.close()

# WebSocket endpoint
@app.websocket("/ws/tutor/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await manager.connect(websocket, user_id)
    print(f"WebSocket connected for user: {user_id}")
    try:
        while True:
            data = await websocket.receive_text()
            print(f"Received raw data: {data}")
            message = json.loads(data)
            print(f"Parsed message: {message}")
            await handle_message(user_id, message, manager)
    except WebSocketDisconnect:
        print(f"WebSocket disconnected for user: {user_id}")
        manager.disconnect(user_id)

@app.delete("/api/lesson_context/{user_id}/{topic}")
async def clear_lesson_context(user_id: str, topic: str):
    rdb = redis.from_url(REDIS_URL, decode_responses=True)
    try:
        topic_key = topic.replace(' ', '_').lower()
        await rdb.delete(f"lesson_context:{user_id}:{topic_key}")
        await rdb.delete(f"assessment:{user_id}:{topic_key}")
        return {"message": "Context cleared successfully"}
    except Exception as e:
        return {"error": "Failed to clear context"}
    finally:
        await rdb.close()

@app.get("/api/conversations/{user_id}")
async def get_conversations(user_id: str):
    rdb = redis.from_url(REDIS_URL, decode_responses=True)
    try:
        user_conversations = await rdb.get(f"user_conversations:{user_id}")
        if user_conversations:
            conversations = json.loads(user_conversations)
            
            for conv in conversations:
                chat_history = await rdb.get(f"chat_history:{user_id}:{conv['topic']}")
                if chat_history:
                    conv['chat_history'] = json.loads(chat_history)
                else:
                    conv['chat_history'] = []
            return {"conversations": conversations}
        return {"conversations": []}
    except Exception as e:
        return {"conversations": []}
    finally:
        await rdb.close()


@app.get("/api/analytics/{user_id}")
async def get_analytics(user_id: str):
    rdb = redis.from_url(REDIS_URL, decode_responses=True)
    try:
        print(f"Getting analytics for user_id: {user_id}")
        
        
        user_conversations = await rdb.get(f"user_conversations:{user_id}")
        conversations = json.loads(user_conversations) if user_conversations else []
        print(f"Found {len(conversations)} conversations")
        
        assessment_keys = await rdb.keys(f"assessment_result:{user_id}:*")
        assessment_results = []
        print(f"Found {len(assessment_keys)} assessment keys for user {user_id}")
        
        for key in assessment_keys:
            result_data = await rdb.get(key)
            if result_data:
                assessment_results.append(json.loads(result_data))
       
        total_lessons = len(conversations)
        assessments_taken = len(assessment_results)
        print(f"Analytics: {total_lessons} lessons, {assessments_taken} assessments")
        
        if assessment_results:
            total_score = sum(result.get('score', 0) for result in assessment_results)
            average_score = round(total_score / assessments_taken, 1)
        else:
            average_score = 0
        
        topics_studied = list(set(conv.get('topic', 'Unknown') for conv in conversations))
        
        recent_assessments = sorted(
            assessment_results, 
            key=lambda x: x.get('timestamp', 0), 
            reverse=True
        )[:5]
        
        return {
            "total_lessons": total_lessons,
            "assessments_taken": assessments_taken,
            "average_score": average_score,
            "topics_studied": topics_studied,
            "recent_assessments": recent_assessments,
            "pass_rate": round(
                len([r for r in assessment_results if r.get('score', 0) >= 60]) / max(assessments_taken, 1) * 100, 1
            ) if assessments_taken > 0 else 0
        }
    finally:
        await rdb.close()

@app.get("/")
async def root():
    return {"status": "LangGraph Tutoring API is running"}


@app.post("/auth/login")
async def login(user_data: UserLogin):
    username = user_data.email.split('@')[0]
    user_id = f"user_{username}"  
    token = str(uuid.uuid4())
    
    return {
        "access_token": token,
        "user": {
            "id": user_id,
            "username": username,
            "email": user_data.email
        }
    }

@app.post("/auth/register")
async def register(user_data: UserCreate):
    user_id = f"user_{user_data.username}" 
    token = str(uuid.uuid4())
    
    return {
        "access_token": token,
        "user": {
            "id": user_id,
            "username": user_data.username,
            "email": user_data.email
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
