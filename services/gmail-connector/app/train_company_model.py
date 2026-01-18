"""
Training script for company name extraction model
Runs periodically to improve accuracy from existing application data
"""
import logging
from app.database import SessionLocal, Application
from app.company_model import CompanyNameModel

logger = logging.getLogger(__name__)

def train_company_model():
    """Train company name model from existing application data"""
    db = SessionLocal()
    try:
        # Fetch all applications with company names
        applications = db.query(Application).filter(
            Application.company_name.isnot(None),
            Application.company_name != 'Unknown Company'
        ).limit(10000).all()  # Limit to prevent memory issues
        
        logger.info(f"Training on {len(applications)} applications")
        
        # Prepare training data
        training_data = []
        for app in applications:
            training_data.append({
                'subject': app.subject or '',
                'from_email': app.from_email or '',
                'snippet': app.snippet or '',
                'company_name': app.company_name or ''
            })
        
        # Train model
        model = CompanyNameModel()
        model.train_from_data(training_data)
        
        logger.info("Company name model training completed")
        
    except Exception as e:
        logger.error(f"Error training company model: {e}", exc_info=True)
    finally:
        db.close()

if __name__ == "__main__":
    train_company_model()
