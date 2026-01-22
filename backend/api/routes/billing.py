"""Billing routes for Stripe integration."""

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from backend.api.dependencies import CurrentUser, DBSession
from backend.config import settings

router = APIRouter()


class SubscriptionInfo(BaseModel):
    """Subscription info response."""

    tier: str
    status: str
    stripe_customer_id: str | None
    stripe_subscription_id: str | None


class CheckoutSession(BaseModel):
    """Checkout session response."""

    session_id: str
    url: str


@router.get("/subscription", response_model=SubscriptionInfo)
async def get_subscription(
    current_user: CurrentUser,
):
    """Get current subscription info."""
    return SubscriptionInfo(
        tier=current_user.subscription_tier,
        status=current_user.subscription_status,
        stripe_customer_id=current_user.stripe_customer_id,
        stripe_subscription_id=current_user.stripe_subscription_id,
    )


@router.post("/checkout")
async def create_checkout_session(
    tier: str,
    db: DBSession,
    current_user: CurrentUser,
):
    """Create Stripe checkout session."""
    if not settings.stripe_secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Billing not configured",
        )

    # Price IDs would be configured in Stripe dashboard
    price_ids = {
        "starter": "price_starter_monthly",
        "professional": "price_professional_monthly",
        "team": "price_team_monthly",
    }

    if tier not in price_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid tier",
        )

    try:
        import stripe

        stripe.api_key = settings.stripe_secret_key

        # Get or create customer
        if current_user.stripe_customer_id:
            customer_id = current_user.stripe_customer_id
        else:
            customer = stripe.Customer.create(
                email=current_user.email,
                metadata={"user_id": str(current_user.id)},
            )
            customer_id = customer.id

            # Update user
            current_user.stripe_customer_id = customer_id
            await db.commit()

        # Create checkout session
        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{
                "price": price_ids[tier],
                "quantity": 1,
            }],
            mode="subscription",
            success_url=f"{settings.app_url}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{settings.app_url}/billing/cancel",
            metadata={"user_id": str(current_user.id)},
        )

        return CheckoutSession(
            session_id=session.id,
            url=session.url,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create checkout session: {str(e)}",
        )


@router.post("/portal")
async def create_portal_session(
    current_user: CurrentUser,
):
    """Create Stripe customer portal session."""
    if not settings.stripe_secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Billing not configured",
        )

    if not current_user.stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No billing account found",
        )

    try:
        import stripe

        stripe.api_key = settings.stripe_secret_key

        session = stripe.billing_portal.Session.create(
            customer=current_user.stripe_customer_id,
            return_url=f"{settings.app_url}/settings/billing",
        )

        return {"url": session.url}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create portal session: {str(e)}",
        )


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    db: DBSession,
):
    """Handle Stripe webhooks."""
    import structlog

    logger = structlog.get_logger(__name__)

    if not settings.stripe_secret_key or not settings.stripe_webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook not configured",
        )

    try:
        import stripe

        stripe.api_key = settings.stripe_secret_key

        payload = await request.body()
        sig_header = request.headers.get("stripe-signature")

        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )

        event_type = event["type"]
        logger.info("Stripe webhook received", event_type=event_type)

        # Handle events
        if event_type == "checkout.session.completed":
            session = event["data"]["object"]
            await _handle_checkout_completed(session, db)

        elif event_type == "customer.subscription.created":
            subscription = event["data"]["object"]
            await _handle_subscription_created(subscription, db)

        elif event_type == "customer.subscription.updated":
            subscription = event["data"]["object"]
            await _handle_subscription_updated(subscription, db)

        elif event_type == "customer.subscription.deleted":
            subscription = event["data"]["object"]
            await _handle_subscription_deleted(subscription, db)

        elif event_type == "invoice.paid":
            invoice = event["data"]["object"]
            await _handle_invoice_paid(invoice, db)

        elif event_type == "invoice.payment_failed":
            invoice = event["data"]["object"]
            await _handle_invoice_payment_failed(invoice, db)

        elif event_type == "customer.updated":
            customer = event["data"]["object"]
            await _handle_customer_updated(customer, db)

        else:
            logger.debug("Unhandled webhook event", event_type=event_type)

        return {"status": "success", "event_type": event_type}

    except stripe.error.SignatureVerificationError:
        logger.warning("Invalid Stripe webhook signature")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid signature",
        )
    except Exception as e:
        logger.error("Webhook processing error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Webhook error: {str(e)}",
        )


# Subscription tier mapping from Stripe price IDs
PRICE_TO_TIER = {
    "price_starter_monthly": "starter",
    "price_professional_monthly": "professional",
    "price_team_monthly": "team",
    "price_enterprise_monthly": "enterprise",
    # Add yearly variants
    "price_starter_yearly": "starter",
    "price_professional_yearly": "professional",
    "price_team_yearly": "team",
    "price_enterprise_yearly": "enterprise",
}


def _get_tier_from_subscription(subscription: dict) -> str:
    """Extract subscription tier from Stripe subscription object."""
    items = subscription.get("items", {}).get("data", [])
    if items:
        price_id = items[0].get("price", {}).get("id", "")
        return PRICE_TO_TIER.get(price_id, "starter")
    return "starter"


async def _handle_checkout_completed(session: dict, db):
    """Handle successful checkout session."""
    import structlog
    from sqlalchemy import select, update
    from backend.storage.timescale.models import User

    logger = structlog.get_logger(__name__)

    user_id = session.get("metadata", {}).get("user_id")
    subscription_id = session.get("subscription")
    customer_id = session.get("customer")

    logger.info(
        "Checkout completed",
        user_id=user_id,
        subscription_id=subscription_id,
    )

    if user_id:
        update_values = {
            "subscription_status": "active",
        }

        if subscription_id:
            update_values["stripe_subscription_id"] = subscription_id
        if customer_id:
            update_values["stripe_customer_id"] = customer_id

        await db.execute(
            update(User)
            .where(User.id == user_id)
            .values(**update_values)
        )
        await db.commit()


async def _handle_subscription_created(subscription: dict, db):
    """Handle new subscription creation."""
    import structlog
    from sqlalchemy import update
    from backend.storage.timescale.models import User

    logger = structlog.get_logger(__name__)

    subscription_id = subscription.get("id")
    customer_id = subscription.get("customer")
    subscription_status = subscription.get("status")
    tier = _get_tier_from_subscription(subscription)

    logger.info(
        "Subscription created",
        subscription_id=subscription_id,
        status=subscription_status,
        tier=tier,
    )

    await db.execute(
        update(User)
        .where(User.stripe_customer_id == customer_id)
        .values(
            stripe_subscription_id=subscription_id,
            subscription_status=subscription_status,
            subscription_tier=tier,
        )
    )
    await db.commit()


async def _handle_subscription_updated(subscription: dict, db):
    """Handle subscription update."""
    import structlog
    from sqlalchemy import update
    from backend.storage.timescale.models import User

    logger = structlog.get_logger(__name__)

    subscription_id = subscription.get("id")
    subscription_status = subscription.get("status")
    tier = _get_tier_from_subscription(subscription)

    # Check for cancellation at period end
    cancel_at_period_end = subscription.get("cancel_at_period_end", False)
    if cancel_at_period_end:
        subscription_status = "canceling"

    logger.info(
        "Subscription updated",
        subscription_id=subscription_id,
        status=subscription_status,
        tier=tier,
    )

    await db.execute(
        update(User)
        .where(User.stripe_subscription_id == subscription_id)
        .values(
            subscription_status=subscription_status,
            subscription_tier=tier,
        )
    )
    await db.commit()


async def _handle_subscription_deleted(subscription: dict, db):
    """Handle subscription cancellation."""
    import structlog
    from sqlalchemy import update
    from backend.storage.timescale.models import User

    logger = structlog.get_logger(__name__)

    subscription_id = subscription.get("id")

    logger.info("Subscription deleted", subscription_id=subscription_id)

    await db.execute(
        update(User)
        .where(User.stripe_subscription_id == subscription_id)
        .values(
            subscription_status="canceled",
            subscription_tier="starter",
            stripe_subscription_id=None,
        )
    )
    await db.commit()


async def _handle_invoice_paid(invoice: dict, db):
    """Handle successful invoice payment."""
    import structlog
    from sqlalchemy import update
    from backend.storage.timescale.models import User

    logger = structlog.get_logger(__name__)

    subscription_id = invoice.get("subscription")
    customer_id = invoice.get("customer")

    logger.info(
        "Invoice paid",
        subscription_id=subscription_id,
        amount=invoice.get("amount_paid"),
    )

    # Ensure subscription is active
    if subscription_id:
        await db.execute(
            update(User)
            .where(User.stripe_subscription_id == subscription_id)
            .values(subscription_status="active")
        )
        await db.commit()


async def _handle_invoice_payment_failed(invoice: dict, db):
    """Handle failed invoice payment."""
    import structlog
    from sqlalchemy import select, update
    from backend.storage.timescale.models import User
    from backend.notifications.email_service import email_service

    logger = structlog.get_logger(__name__)

    subscription_id = invoice.get("subscription")
    customer_id = invoice.get("customer")
    attempt_count = invoice.get("attempt_count", 0)

    logger.warning(
        "Invoice payment failed",
        subscription_id=subscription_id,
        attempt_count=attempt_count,
    )

    # Update subscription status
    if subscription_id:
        await db.execute(
            update(User)
            .where(User.stripe_subscription_id == subscription_id)
            .values(subscription_status="past_due")
        )
        await db.commit()

        # Send notification email
        result = await db.execute(
            select(User).where(User.stripe_subscription_id == subscription_id)
        )
        user = result.scalar_one_or_none()

        if user and user.email:
            email_service.send_email(
                to_email=user.email,
                subject="Payment Failed - Action Required",
                html_body=f"""
                <h2>Payment Failed</h2>
                <p>We were unable to process your subscription payment.</p>
                <p>Please update your payment method to continue using premium features.</p>
                <p><a href="{settings.app_url}/settings/billing">Update Payment Method</a></p>
                """,
            )


async def _handle_customer_updated(customer: dict, db):
    """Handle customer update (e.g., email change)."""
    import structlog
    from sqlalchemy import update
    from backend.storage.timescale.models import User

    logger = structlog.get_logger(__name__)

    customer_id = customer.get("id")
    email = customer.get("email")

    logger.debug("Customer updated", customer_id=customer_id)

    # We don't update email here as it should be managed through our own system
    # But log for auditing purposes
