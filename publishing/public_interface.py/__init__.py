"""
publishing/ -- Public interface
===================================
(Planned -- not yet built)
Handles actual posting to social platforms after content is generated.

Planned modules:
    instagram_publisher.py  -- Posts via Instagram Graph API
    linkedin_publisher.py   -- Posts via LinkedIn API
    tiktok_publisher.py     -- Posts via TikTok API
    youtube_publisher.py    -- Uploads via YouTube Data API
    facebook_publisher.py   -- Posts via Facebook Graph API
    scheduler.py            -- Queue posts for a specific time
    publisher_registry.py   -- PUBLISHER_MAP + get_publisher(platform)

Integration point:
    main.py's run() would call publisher after format_output() if
    state.get("auto_publish") is True and credentials are present.
"""