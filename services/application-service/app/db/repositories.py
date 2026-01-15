from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, desc, func, or_
from app.models import Application, Company, Role, StatusHistory, User
from typing import List, Optional
from datetime import datetime
import logging
import uuid

logger = logging.getLogger(__name__)

class ApplicationRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create_company(self, name: str) -> Company:
        normalized_name = name.lower().strip()
        company = self.db.execute(select(Company).where(Company.name == normalized_name)).scalar_one_or_none()
        if not company:
            company = Company(name=normalized_name)
            self.db.add(company)
            self.db.flush()
        return company

    def get_or_create_role(self, company_id: str, title: str) -> Role:
        normalized_title = title.lower().strip()
        role = self.db.execute(select(Role).where(
            Role.company_id == company_id, 
            Role.title == normalized_title
        )).scalar_one_or_none()
        
        if not role:
            role = Role(company_id=company_id, title=normalized_title)
            self.db.add(role)
            self.db.flush()
        return role

    def upsert_application(self, 
                           company_id: str, 
                           role_id: str, 
                           status: str, 
                           confidence: float = 0.0,
                           email_date: datetime = None,
                           user_id = None) -> Application:
        
        # CRITICAL: Filter by user_id to prevent cross-user deduplication
        # Same company+role for different users = different applications
        query = select(Application).where(
            Application.company_id == company_id,
            Application.role_id == role_id
        )
        
        # REQUIREMENT: Multi-user support - filter by user_id
        if user_id:
            try:
                user_id_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
                query = query.where(Application.user_id == user_id_uuid)
                logger.info(f"🔍 [REPO] Looking for application: company_id={company_id}, role_id={role_id}, user_id={user_id_uuid}")
            except (ValueError, TypeError) as e:
                logger.warning(f"⚠️ [REPO] Invalid user_id format: {user_id}, error: {e}")
                # Also check for NULL user_id (backward compatibility)
                query = query.where(
                    or_(
                        Application.user_id.is_(None),
                        Application.user_id == user_id
                    )
                )
        else:
            # If no user_id provided, only match applications with NULL user_id (backward compatibility)
            query = query.where(Application.user_id.is_(None))
            logger.info(f"🔍 [REPO] Looking for application (no user_id): company_id={company_id}, role_id={role_id}")
        
        app = self.db.execute(query).scalar_one_or_none()
        
        if app:
            # Update user_id if it's None and we have one
            if app.user_id is None and user_id is not None:
                app.user_id = user_id
                self.db.commit()
                self.db.refresh(app)
            # Update logic is handled by caller (UpsertLogic) usually, 
            # but repository just saves the object. 
            # We return existing to let Logic decide.
            return app
        else:
            new_app = Application(
                company_id=company_id,
                role_id=role_id,
                status=status,
                status_confidence=confidence,
                last_email_date=email_date or datetime.utcnow(),
                applied_count=1,
                user_id=user_id  # CRITICAL: Set user_id when creating
            )
            self.db.add(new_app)
            self.db.commit()
            self.db.refresh(new_app)
            
            # Initial status history
            self.log_status_change(new_app.id, status, None)
            return new_app

    def update_application_status(self, app_id: str, new_status: str) -> Optional[Application]:
        app = self.db.execute(select(Application).where(Application.id == app_id)).scalar_one_or_none()
        if app and app.status != new_status:
            old_status = app.status
            app.status = new_status
            app.updated_at = datetime.utcnow()
            self.db.add(app)
            # Log history
            self.log_status_change(app_id, new_status, old_status)
            self.db.commit()
            self.db.refresh(app)
        return app
        
    def log_status_change(self, app_id: str, new_status: str, old_status: Optional[str]):
        history = StatusHistory(
            application_id=app_id,
            status=new_status,
            previous_status=old_status
        )
        self.db.add(history)

    def list_applications(self, user_id: Optional[str] = None, limit: Optional[int] = None) -> List[Application]:
        """
        REQUIREMENT 6 & 9: List applications for a user.
        
        - If user_id provided: Returns ALL applications for that user (no limit)
        - If user_id is None: Returns ALL applications (backward compatibility)
        - Sorted by last_email_date DESC (most recent first)
        - Eagerly loads relationships to avoid lazy loading issues
        """
        # Use joinedload to eagerly load relationships and avoid N+1 queries
        query = select(Application).options(
            joinedload(Application.company),
            joinedload(Application.role),
            joinedload(Application.resume)
        ).order_by(desc(Application.last_email_date))  # REQUIREMENT 6: Most recent first
        
        # REQUIREMENT 9: Filter by user_id if provided
        # CRITICAL: Also include applications with NULL user_id for backward compatibility
        if user_id:
            try:
                user_id_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
                # Include applications with this user_id OR applications with NULL user_id (backward compatibility)
                from sqlalchemy import or_
                query = query.where(
                    or_(
                        Application.user_id == user_id_uuid,
                        Application.user_id.is_(None)  # Include NULL user_id for backward compatibility
                    )
                )
                logger.info(f"🔍 [REPO] Filtering: user_id={user_id_uuid} OR user_id IS NULL")
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid user_id format: {user_id}, error: {e}")
                # Continue without filtering (backward compatibility)
        
        # REQUIREMENT 6: No limit - show ALL applications for the user
        if limit:
            logger.warning(f"⚠️ [REPO] LIMIT {limit} applied - this may restrict results!")
            query = query.limit(limit)
        else:
            logger.info(f"✅ [REPO] NO LIMIT - returning ALL applications for user {user_id or 'ALL'}")
        
        # CRITICAL: Before executing, log the query details
        if limit:
            logger.warning(f"⚠️ [REPO] LIMIT {limit} will be applied!")
        else:
            logger.info(f"✅ [REPO] NO LIMIT - query will return ALL matching applications")
        
        # CRITICAL: Execute query and handle joinedload duplicates
        # Use unique() to handle joinedload duplicates, but be careful - it might filter out valid records
        try:
            result = self.db.execute(query).unique().scalars().all()
            result_list = list(result)
        except Exception as e:
            logger.error(f"❌ [REPO] Error executing query: {e}", exc_info=True)
            # Fallback: try without unique() if it's causing issues
            try:
                result = self.db.execute(query).scalars().all()
                result_list = list(result)
                # Manual deduplication by ID
                seen_ids = set()
                deduplicated = []
                for app in result_list:
                    if app.id not in seen_ids:
                        seen_ids.add(app.id)
                        deduplicated.append(app)
                result_list = deduplicated
                logger.warning(f"⚠️ [REPO] Used manual deduplication instead of unique()")
            except Exception as e2:
                logger.error(f"❌ [REPO] Fallback query also failed: {e2}", exc_info=True)
                return []
        
        # CRITICAL DEBUG: Also check total count in DB for comparison
        count_query = select(func.count(Application.id))
        if user_id:
            try:
                user_id_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
                # Count applications with this user_id OR NULL user_id
                from sqlalchemy import or_
                count_query = count_query.where(
                    or_(
                        Application.user_id == user_id_uuid,
                        Application.user_id.is_(None)
                    )
                )
                logger.info(f"🔍 [REPO DEBUG] Counting applications for user_id: {user_id_uuid} OR NULL")
            except Exception as e:
                logger.warning(f"⚠️ [REPO] Invalid user_id format for count: {user_id}, error: {e}")
        else:
            logger.info(f"🔍 [REPO DEBUG] Counting ALL applications (no user_id filter)")
        
        # Also count total in DB (no filters) for comparison
        total_all_query = select(func.count(Application.id))
        total_all = self.db.execute(total_all_query).scalar() or 0
        logger.info(f"🔍 [REPO DEBUG] Total applications in DB (all users, no filters): {total_all}")
        
        total_count = self.db.execute(count_query).scalar() or 0
        
        logger.info(f"📊 [REPO] Query returned {len(result_list)} applications")
        logger.info(f"📊 [REPO] Total count in DB (for comparison): {total_count}")
        logger.info(f"📊 [REPO] User filter: {user_id or 'NONE (all users)'}")
        logger.info(f"📊 [REPO] Limit applied: {limit or 'NONE (unlimited)'}")
        
        if len(result_list) != total_count and not limit:
            logger.error(f"❌ [REPO] MISMATCH: Query returned {len(result_list)} but DB has {total_count} total!")
            logger.error(f"❌ [REPO] This suggests a query issue, relationship filtering problem, or user_id mismatch")
            logger.error(f"❌ [REPO] Possible causes:")
            logger.error(f"   - Applications don't have user_id set (NULL)")
            logger.error(f"   - user_id format mismatch")
            logger.error(f"   - joinedload().unique() filtering out valid records")
        
        return result_list
    
    def get_by_id(self, app_id: str) -> Optional[Application]:
        return self.db.execute(select(Application).where(Application.id == app_id)).scalar_one_or_none()
