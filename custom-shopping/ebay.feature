Feature: ebay
    @app
    Scenario: show more!
        Given screen is app_filter_showmore
        Then click !marked:'Show more'
