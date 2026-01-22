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
            success_url="https://yourdomain.com/billing/success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url="https://yourdomain.com/billing/cancel",
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
            return_url="https://yourdomain.com/settings/billing",
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

        # Handle events
        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]
            await _handle_checkout_completed(session, db)

        elif event["type"] == "customer.subscription.updated":
            subscription = event["data"]["object"]
            await _handle_subscription_updated(subscription, db)

        elif event["type"] == "customer.subscription.deleted":
            subscription = event["data"]["object"]
            await _handle_subscription_deleted(subscription, db)

        return {"status": "success"}

    except stripe.error.SignatureVerificationError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid signature",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Webhook error: {str(e)}",
        )


async def _handle_checkout_completed(session: dict, db):
    """Handle successful checkout."""
    from sqlalchemy import select, update
    from backend.storage.timescale.models import User

    user_id = session.get("metadata", {}).get("user_id")
    subscription_id = session.get("subscription")

    if user_id and subscription_id:
        await db.execute(
            update(User)
            .where(User.id == user_id)
            .values(
                stripe_subscription_id=subscription_id,
                subscription_status="active",
            )
        )
        await db.commit()


async def _handle_subscription_updated(subscription: dict, db):
    """Handle subscription update."""
    from sqlalchemy import update
    from backend.storage.timescale.models import User

    subscription_id = subscription.get("id")
    status = subscription.get("status")

    await db.execute(
        update(User)
        .where(User.stripe_subscription_id == subscription_id)
        .values(subscription_status=status)
    )
    await db.commit()


async def _handle_subscription_deleted(subscription: dict, db):
    """Handle subscription cancellation."""
    from sqlalchemy import update
    from backend.storage.timescale.models import User

    subscription_id = subscription.get("id")

    await db.execute(
        update(User)
        .where(User.stripe_subscription_id == subscription_id)
        .values(
            subscription_status="canceled",
            subscription_tier="starter",
        )
    )
    await db.commit()
