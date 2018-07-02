Feature: 5miles
    @app
    Scenario: disallow contact access
        Given screen is app_5miles_contractprompt
        When click !marked:'skip'

    @app
    Scenario: don't follow users
        Given screen is app_5miles_followusers
        When click !marked:'Navigate up'

    @override
    Scenario: sort by price increasing [with confirm, on filter screen]
        Given screen is filter
        When click @sort_pricelow
        And click @apply
        Then screen is searchret

    @override
    Scenario: sort by price decreasing [with confirm, on filter screen]
        Given screen is filter
        When click @sort_pricehigh
        And click @apply
        Then screen is searchret

    @override
    Scenario: sort by recent [with confirm step, on filter screen]
        Given screen is filter
        When click @sort_recent
        And click @apply
        Then screen is searchret

