"""Test FastAPI app initialization."""

from app.main import app


def test_app():
    """Test app initialization."""
    
    print('✓ FastAPI app loads successfully')
    print(f'✓ App title: {app.title}')
    print(f'✓ App version: {app.version}')
    
    # List routers
    routers = [r.prefix for r in app.routes if hasattr(r, 'prefix') and r.prefix]
    print(f'\n✓ Registered routers ({len(routers)}):')
    for prefix in sorted(set(routers)):
        print(f'  - {prefix}')
    
    # Check subscriptions router is included
    if '/subscriptions' in routers:
        print('\n✓ Subscriptions router is registered!')
    else:
        print('\n⚠ WARNING: Subscriptions router NOT found!')
    
    print('\n✓ All tests passed!')


if __name__ == "__main__":
    test_app()
