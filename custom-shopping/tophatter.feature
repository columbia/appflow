Feature: tophatter
    @app
    Scenario: skip live screen
        Given screen is app_tophatter_live
        Then click !marked:'Browse'
        Then screen is main
