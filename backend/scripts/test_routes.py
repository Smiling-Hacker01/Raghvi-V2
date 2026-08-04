"""Test API routes."""

from app.main import app


def test_routes():
    """Test routes."""

    print("✓ FastAPI app initialized")

    # Get all routes
    routes = []
    for route in app.routes:
        if hasattr(route, "path") and hasattr(route, "methods"):
            routes.append((route.path, route.methods, route.name))

    print(f"\n✓ Total routes: {len(routes)}")

    # Find subscription routes
    subscription_routes = [r for r in routes if "/subscriptions" in r[0]]

    if subscription_routes:
        print(f"\n✓ Subscription routes found ({len(subscription_routes)}):")
        for path, methods, name in subscription_routes:
            print(f"  {list(methods)[0]:6} {path:40} {name}")
    else:
        print("\n⚠ No subscription routes found")

    # Check for other key routes
    print("\n✓ Sample routes:")
    for path, methods, name in routes[:10]:
        method = list(methods)[0] if methods else "N/A"
        print(f"  {method:6} {path:40} {name}")

    print("\n✓ Tests complete!")


if __name__ == "__main__":
    test_routes()
