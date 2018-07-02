Feature: etsy
    @app
    Scenario: skip category in searchret
        Given screen is app_etsy_searchcat
        Then scroll down

    @app
    Scenario: select a size
        Given screen is app_etsy_option
        Then click !marked:'Select a size'
        And click !id:'text1'
