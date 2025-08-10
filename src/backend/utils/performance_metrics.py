import time
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
import json

logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetrics:
    """Focused performance metrics for VoiceBot Classic conversations."""
    
    # Core Performance Metrics
    response_latency_ms: float = 0.0
    speech_to_text_latency_ms: float = 0.0
    text_to_speech_latency_ms: float = 0.0
    temperature: float = 0.0
    model: str = ""
    system_message: str = ""
    
    # Conversation Quality Metrics
    message_count: int = 0
    conversation_duration_ms: float = 0.0
    session_start_time: str = ""
    session_end_time: str = ""
    
    # User Experience Metrics
    customer_sentiment: int = 0  # 1-5 scale (1=very unsatisfied, 5=very satisfied)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary for CosmosDB storage."""
        return asdict(self)
    
    def update_conversation_duration(self):
        """Calculate and update conversation duration."""
        if self.session_start_time and self.session_end_time:
            start = datetime.fromisoformat(self.session_start_time.replace('Z', '+00:00'))
            end = datetime.fromisoformat(self.session_end_time.replace('Z', '+00:00'))
            self.conversation_duration_ms = (end - start).total_seconds() * 1000

class PerformanceTracker:
    """Tracks focused performance metrics for VoiceBot Classic sessions."""
    
    def __init__(self):
        self.metrics = PerformanceMetrics()
        self.response_start_time = None
        self.stt_start_time = None
        self.tts_start_time = None
        self.stt_count = 0
        self.tts_count = 0
    
    def start_session(self):
        """Mark the start of a conversation session."""
        self.metrics.session_start_time = datetime.now(timezone.utc).isoformat()
        logger.debug("Performance tracking session started")
    
    def end_session(self):
        """Mark the end of a conversation session."""
        self.metrics.session_end_time = datetime.now(timezone.utc).isoformat()
        self.metrics.update_conversation_duration()
        logger.debug("Performance tracking session ended")
    
    def start_response_timing(self):
        """Mark the start of AI response generation."""
        self.response_start_time = time.time()
    
    def end_response_timing(self):
        """Mark the end of AI response generation."""
        if self.response_start_time:
            duration = (time.time() - self.response_start_time) * 1000
            self.metrics.response_latency_ms += duration
            self.response_start_time = None
    
    def start_speech_to_text(self):
        """Mark the start of speech-to-text processing."""
        self.stt_start_time = time.time()
    
    def end_speech_to_text(self):
        """Mark the end of speech-to-text processing."""
        if self.stt_start_time:
            duration = (time.time() - self.stt_start_time) * 1000
            self.metrics.speech_to_text_latency_ms += duration
            self.stt_count += 1
            self.stt_start_time = None
    
    def start_text_to_speech(self):
        """Mark the start of text-to-speech processing."""
        self.tts_start_time = time.time()
    
    def end_text_to_speech(self):
        """Mark the end of text-to-speech processing."""
        if self.tts_start_time:
            duration = (time.time() - self.tts_start_time) * 1000
            self.metrics.text_to_speech_latency_ms += duration
            self.tts_count += 1
            self.tts_start_time = None
    
    def increment_message_count(self):
        """Increment the message count."""
        self.metrics.message_count += 1
    
    def update_model_parameters(self, temperature: float, system_instruction: str, model: str):
        """Update model performance parameters."""
        self.metrics.temperature = temperature
        self.metrics.system_message = system_instruction
        self.metrics.model = model
    
    def set_customer_sentiment(self, sentiment: int):
        """Set customer sentiment score (1-5)."""
        if 1 <= sentiment <= 5:
            self.metrics.customer_sentiment = sentiment
        else:
            logger.warning(f"Invalid sentiment score: {sentiment}. Must be 1-5.")
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get a summary of key performance metrics."""
        avg_response_time = self.metrics.response_latency_ms / max(1, self.metrics.message_count)
        avg_stt_latency = self.metrics.speech_to_text_latency_ms / max(1, self.stt_count)
        avg_tts_latency = self.metrics.text_to_speech_latency_ms / max(1, self.tts_count)
        conversation_duration_min = self.metrics.conversation_duration_ms / 60000 if self.metrics.conversation_duration_ms > 0 else 0
        
        return {
            "avg_response_latency_ms": round(avg_response_time, 2),
            "avg_stt_latency_ms": round(avg_stt_latency, 2),
            "avg_tts_latency_ms": round(avg_tts_latency, 2),
            "temperature": self.metrics.temperature,
            "model": self.metrics.model,
            "system_message": self.metrics.system_message,
            "total_messages": self.metrics.message_count,
            "total_stt_operations": self.stt_count,
            "total_tts_operations": self.tts_count,
            "conversation_duration_min": round(conversation_duration_min, 2),
            "customer_sentiment": self.metrics.customer_sentiment,
            "session_completed": bool(self.metrics.session_end_time)
        }

def save_performance_metrics(conversation_doc: Dict, performance_tracker: PerformanceTracker):
    """Add evaluation metrics summary to conversation document for CosmosDB storage."""
    try:
        summary = performance_tracker.get_metrics_summary()
        
        conversation_doc["evaluation_metrics"] = {
            **summary,
            "collected_at": datetime.now(timezone.utc).isoformat()
        }
        
        logger.info(f"Evaluation metrics added to conversation: {summary}")
        logger.info(f"Conversation document now has keys: {list(conversation_doc.keys())}")
        
    except Exception as e:
        logger.error(f"Error saving evaluation metrics: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")

def analyze_customer_sentiment_from_conversation(client, model_name: str, conversation_history: list) -> int:
    """
    Analyze customer sentiment from the entire conversation using AI.
    Returns sentiment score 1-5 (1=very unsatisfied, 5=very satisfied).
    """
    try:
        # Prepare conversation text for analysis
        conversation_text = ""
        for msg in conversation_history:
            if msg.get("role") == "user":
                conversation_text += f"Customer: {msg.get('content', '')}\n"
            elif msg.get("role") == "assistant":
                conversation_text += f"Assistant: {msg.get('content', '')}\n"
        
        if not conversation_text.strip():
            return 3  # Neutral if no conversation
        
        sentiment_prompt = f"""
Analyze the customer sentiment throughout this conversation and rate it on a scale of 1-5:

1 = Very Unsatisfied (angry, frustrated, unresolved issues)
2 = Unsatisfied (disappointed, concerns not addressed)
3 = Neutral (neither satisfied nor unsatisfied)
4 = Satisfied (content, issues resolved)
5 = Very Satisfied (happy, exceeded expectations)

Conversation:
{conversation_text}

Consider:
- Customer's tone and language throughout the conversation
- Whether their issues were resolved
- Their overall interaction experience
- Any expressions of satisfaction or frustration

Respond with only a single number (1-5) representing the overall customer sentiment.
"""
        
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": sentiment_prompt}],
            temperature=0.1,
            max_tokens=10
        )
        
        sentiment_text = response.choices[0].message.content.strip()
        
        # Extract number from response
        try:
            sentiment_score = int(sentiment_text)
            if 1 <= sentiment_score <= 5:
                return sentiment_score
            else:
                logger.warning(f"Sentiment score out of range: {sentiment_score}")
                return 3
        except ValueError:
            logger.warning(f"Could not parse sentiment score: {sentiment_text}")
            return 3
            
    except Exception as e:
        logger.error(f"Error analyzing customer sentiment: {e}")
        return 3  # Default to neutral
