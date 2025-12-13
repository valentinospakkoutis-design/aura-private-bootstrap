"""
Sentiment Analysis Service
Analyze sentiment from news and text using NLTK
"""

from typing import Dict, Optional, List
from datetime import datetime
import nltk
from nltk.sentiment import SentimentIntensityAnalyzer
from nltk.tokenize import word_tokenize, sent_tokenize
from nltk.corpus import stopwords
import re


class SentimentAnalyzer:
    """
    Sentiment analysis using NLTK VADER
    """
    
    def __init__(self):
        # Download required NLTK data
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            nltk.download('punkt', quiet=True)
        
        try:
            nltk.data.find('vader_lexicon')
        except LookupError:
            nltk.download('vader_lexicon', quiet=True)
        
        try:
            nltk.data.find('corpora/stopwords')
        except LookupError:
            nltk.download('stopwords', quiet=True)
        
        self.analyzer = SentimentIntensityAnalyzer()
        self.stop_words = set(stopwords.words('english'))
    
    def analyze_text(self, text: str) -> Dict:
        """
        Analyze sentiment of text
        
        Args:
            text: Text to analyze
        
        Returns:
            Sentiment scores and label
        """
        if not text:
            return {
                "sentiment_label": "neutral",
                "sentiment_score": 0.0,
                "compound": 0.0,
                "positive": 0.0,
                "negative": 0.0,
                "neutral": 0.0
            }
        
        # Clean text
        text = re.sub(r'[^\w\s]', '', text)
        
        # Analyze sentiment
        scores = self.analyzer.polarity_scores(text)
        
        # Determine label
        compound = scores['compound']
        if compound >= 0.05:
            label = "positive"
        elif compound <= -0.05:
            label = "negative"
        else:
            label = "neutral"
        
        return {
            "sentiment_label": label,
            "sentiment_score": compound,
            "compound": compound,
            "positive": scores['pos'],
            "negative": scores['neg'],
            "neutral": scores['neu']
        }
    
    def analyze_articles(self, articles: List[Dict]) -> Dict:
        """
        Analyze sentiment from multiple articles
        
        Args:
            articles: List of article dicts with 'title' and/or 'summary'
        
        Returns:
            Aggregated sentiment analysis
        """
        if not articles:
            return {
                "sentiment_label": "neutral",
                "sentiment_score": 0.0,
                "article_count": 0
            }
        
        all_texts = []
        for article in articles:
            text = f"{article.get('title', '')} {article.get('summary', '')}"
            if text.strip():
                all_texts.append(text)
        
        if not all_texts:
            return {
                "sentiment_label": "neutral",
                "sentiment_score": 0.0,
                "article_count": len(articles)
            }
        
        # Analyze each article
        sentiments = []
        for text in all_texts:
            sentiment = self.analyze_text(text)
            sentiments.append(sentiment)
        
        # Aggregate
        avg_compound = sum(s['compound'] for s in sentiments) / len(sentiments)
        
        if avg_compound >= 0.05:
            label = "positive"
        elif avg_compound <= -0.05:
            label = "negative"
        else:
            label = "neutral"
        
        return {
            "sentiment_label": label,
            "sentiment_score": round(avg_compound, 3),
            "article_count": len(articles),
            "positive_count": sum(1 for s in sentiments if s['sentiment_label'] == 'positive'),
            "negative_count": sum(1 for s in sentiments if s['sentiment_label'] == 'negative'),
            "neutral_count": sum(1 for s in sentiments if s['sentiment_label'] == 'neutral')
        }


# Global instance
sentiment_analyzer = SentimentAnalyzer()

