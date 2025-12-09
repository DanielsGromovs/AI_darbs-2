import os
from openai import OpenAI
from dotenv import load_dotenv
import httpx
import warnings
from datetime import datetime

# Suppress httpx warnings
warnings.filterwarnings('ignore')

class ChatbotService:
    def __init__(self):
        # TODO: 1. SOLIS - API atslēgas ielāde
        # load_dotenv(), lai ielādētu mainīgos no .env faila.
        # os.getenv(), lai nolasītu "HUGGINGFACE_API_KEY".
        load_dotenv()
        api_key = os.getenv("HUGGINGFACE_API_KEY")

        # TODO: 2. SOLIS - OpenAI klienta inicializācija izmantojot "katanemo/Arch-Router-1.5B" modeli
        # Saglabājam klienta inicializāciju (ja nākotnē vēlēsies ārēju modeli),
        # taču pašlaik atbildes tiek ģenerētas lokāli, lai izvairītos no 410 kļūdām.
        try:
            http_client = httpx.Client(timeout=60.0)
            self.client = OpenAI(
                api_key=api_key,
                base_url="https://api-inference.huggingface.co/openai/",
                http_client=http_client
            )
        except Exception as e:
            print(f"Warning: OpenAI client not available (using local responses): {e}")
            self.client = None

        # TODO: 3. SOLIS - Sistēmas instrukcijas definēšana
        self.system_instruction = (
            "You are a friendly, concise e-commerce assistant for 'My E-Shop'.\n"
            "Site highlights: hero tagline 'Your one-stop shop for amazing products', best deals, simple checkout.\n"
            "Navigation: Home, Shop, Cart, History, Account (Login/Register/Logout), Admin (for admins).\n"
            "Checkout note: payment is mock — no real charges occur.\n"
            "Your job:\n"
            "- Greet naturally, be brief, propose next helpful action.\n"
            "- Answer only about this shop: products, prices, stock, cart, orders, checkout, account.\n"
            "- If off-topic (weather, politics, sports, etc.), gently steer back to shopping.\n"
            "- When relevant, mention products from the current catalog and invite to view the Shop page.\n"
            "- Keep answers short (1-3 sentences).\n"
            "- If info is unknown, say so and propose to browse the shop.\n"
        )

    def get_chatbot_response(self, user_message, chat_history=None, products=None):
        """Return a natural, shop-aware response without external API calls."""
        if chat_history is None:
            chat_history = []

        # Normalise inputs
        user_lower = user_message.lower().strip()
        products = products or []

        # Build helpful snippets from catalog
        catalog_text = self._format_product_catalog(products)
        product_names = [p.get("name", "") for p in products]

        # Quick helpers
        def list_some_products(limit=4):
            names = [p.get("name", "") for p in products if p.get("name")]
            if not names:
                return "We have a rotating catalog—open the Shop page to see what's available now."
            shown = names[:limit]
            more = "" if len(names) <= limit else " and more"
            return "We currently feature: " + ", ".join(shown) + more + "."

        def price_range_text():
            if not products:
                return "Browse the Shop page to see current prices."
            cheapest = min(products, key=lambda p: p.get("price", 0))
            most_expensive = max(products, key=lambda p: p.get("price", 0))
            return (
                f"Prices start at ${cheapest.get('price', 0):.2f} "
                f"and go up to ${most_expensive.get('price', 0):.2f}."
            )

        def find_product_match(message):
            for p in products:
                name = p.get("name", "").lower()
                if name and name in message:
                    return p
            return None

        # Off-topic guardrail
        off_topic_words = ["weather", "sport", "politic", "movie", "music", "game", "news"]
        if any(w in user_lower for w in off_topic_words):
            return {
                "response": (
                    "I'm here for My E-Shop questions—products, prices, stock, cart, or checkout. "
                    "Tell me what you're looking for and I'll help."
                )
            }

        # Intent handling
        if any(greet in user_lower for greet in ["hi", "hello", "hey", "greetings"]):
            return {
                "response": f"Hi! Welcome to My E-Shop. {list_some_products()} Want me to point you to a deal?"
            }

        if "product" in user_lower or "shop" in user_lower or "catalog" in user_lower:
            return {"response": list_some_products() + " Check the Shop page for full details and photos."}

        if any(word in user_lower for word in ["price", "cost", "how much", "expensive", "cheap"]):
            return {"response": price_range_text() + " Need a specific item? Tell me the name."}

        if any(word in user_lower for word in ["stock", "available", "availability", "left"]):
            match = find_product_match(user_lower)
            if match:
                return {
                    "response": (
                        f"{match.get('name')} has {match.get('stock', 0)} in stock at ${match.get('price', 0):.2f}. "
                        "Add it to cart from the product page."
                    )
                }
            return {"response": "Stock changes quickly—open the Shop page to see live availability."}

        if any(word in user_lower for word in ["laptop", "mouse", "keyboard", "phone", "tablet"]):
            match = find_product_match(user_lower)
            if match:
                desc = match.get("description") or "Solid choice for everyday use."
                return {
                    "response": (
                        f"{match.get('name')} is ${match.get('price', 0):.2f} with {match.get('stock', 0)} in stock. "
                        f"{desc} Want a link to it?"
                    )
                }
            return {"response": list_some_products() + " Tell me which one interests you."}

        if "checkout" in user_lower or "pay" in user_lower or "order" in user_lower or "cart" in user_lower:
            return {
                "response": (
                    "Add items to your cart, then go to Checkout. Payments are mock here—no real charges. "
                    "Want help finding an item first?"
                )
            }

        if "account" in user_lower or "login" in user_lower or "register" in user_lower or "sign" in user_lower:
            return {
                "response": "You can log in or register from the top navigation. Need a link?"
            }

        if "history" in user_lower or "order history" in user_lower:
            return {"response": "Open the History page to see your past orders. Can I help find something again?"}

        # Default helpful response using catalog summary
        if products:
            return {
                "response": (
                    f"I can help with My E-Shop products and orders. {list_some_products()} "
                    "Ask me about price or availability, and I'll check."
                )
            }

        return {
            "response": (
                "I can help with My E-Shop products, prices, stock, cart, and checkout. "
                "Tell me what you need and I'll guide you."
            )
        }
    
    def _format_product_catalog(self, products):
        """Format products into a readable catalog string for the AI model"""
        if not products:
            return "PRODUCT CATALOG: Currently, no products are available in our store."
        
        catalog = "\n\nCURRENT PRODUCT CATALOG:\n"
        catalog += "=" * 60 + "\n"
        
        for product in products:
            catalog += f"\nProduct: {product.get('name', 'Unknown')}\n"
            catalog += f"  - Price: ${product.get('price', 0):.2f}\n"
            catalog += f"  - Stock: {product.get('stock', 0)} units available\n"
            if product.get('description'):
                catalog += f"  - Description: {product.get('description')}\n"
        
        catalog += "\n" + "=" * 60
        return catalog
    
    def _generate_fallback_response(self, user_message, products=None):
        """Generate a keyword-based response with domain restriction for e-commerce"""
        user_lower = user_message.lower()
        
        # Domain restriction: Check if the message is e-commerce related
        non_ecommerce_keywords = ['weather', 'sports', 'politics', 'news', 'movie', 'game', 'music']
        is_non_ecommerce = any(keyword in user_lower for keyword in non_ecommerce_keywords)
        
        # Product-related responses
        if any(word in user_lower for word in ['hello', 'hi', 'hey', 'greetings']):
            return "Hello! Welcome to our e-commerce store. How can I assist you today?"
        
        elif any(word in user_lower for word in ['product', 'item', 'buy', 'shop', 'browse']):
            if products:
                product_names = ", ".join([p.get('name') for p in products[:3]])
                return f"We have several great products available including: {product_names}. Would you like to know more about any of these?"
            return "We have a great selection of products available. Would you like to browse our shop or search for something specific?"
        
        elif any(word in user_lower for word in ['price', 'cost', 'expensive', 'cheap', 'how much']):
            if products:
                cheapest = min(products, key=lambda p: p.get('price', 0))
                most_expensive = max(products, key=lambda p: p.get('price', 0))
                return f"Our products range from ${cheapest.get('price', 0):.2f} to ${most_expensive.get('price', 0):.2f}. Which price range interests you?"
            return "Our prices are competitive and we offer great value. Feel free to explore our products to find what fits your budget."
        
        elif any(word in user_lower for word in ['help', 'support', 'assist', 'question']):
            return "I'm here to help! What would you like assistance with? You can ask about products, orders, shopping, or anything e-commerce related."
        
        elif any(word in user_lower for word in ['order', 'purchase', 'checkout', 'cart']):
            return "Great! Would you like to browse our products or proceed to checkout? Let me know how I can help with your order."
        
        elif any(word in user_lower for word in ['thank', 'thanks', 'appreciate']):
            return "You're welcome! Is there anything else I can help you with? Feel free to ask about our products or services."
        
        elif is_non_ecommerce:
            return "I appreciate your question, but I'm specifically designed to help with our e-commerce store. I can answer questions about our products, prices, orders, and shopping. Is there anything store-related I can help you with?"
        
        else:
            return f"Thanks for your message. I'm here to help with our e-commerce store. Could you tell me what you're looking for? Would you like to browse products, check prices, or get help with an order?"
