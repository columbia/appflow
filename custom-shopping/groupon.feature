Feature: groupon

    @app
    Scenario: pass intro
        Given screen is app_groupon_intro
        #click !marked:'Select Country'
        #click !marked:'United States'
        Then text !id:'action_bar_search_edittext' '10027'
        And click !id:'search_suggestions_list_item'

    @app
    Scenario: select option
        Given screen is app_groupon_option
        Then click !id:'option_image'

    @override
    @bridge
    Scenario: goto filter, scroll first
        Given screen is searchret
        And searched is true
        When scrollit !id:'exposed_filters_scroll_view' right
        And click !textcontains:'^ALL FILTERS'
        Then screen is filter

    @bridge
    Scenario: add payment method
        Given screen is cart
        And cart_filled is true
        When click Add Payment Method
        Then screen is payment

    @bridge
    Scenario: add shipping address
        Given screen is cart
        And cart_filled is true
        When click shipping_icon
        Then screen is addredit

    @override
    @bridge
    Scenario: goto sort, scroll first
        Given screen is searchret
        And searched is true
        When scrollit !id:'exposed_filters_scroll_view' right
        And click !textcontains:'^Sort By'
        Then screen is sort


