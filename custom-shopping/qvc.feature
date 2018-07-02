Feature: qvc

    @app
    Scenario: accept license
        Given screen is app_qvc_license
        Then click !marked:'ACCEPT'

    @override
    @bridge
    Scenario: remove through edit
        Given screen is cart
        And cart_filled is true
        When click !id:'btnEditDone'
        And click !id:'chkDelete'
        And click !id:'btnDeleteMultiple'
        Then screen is cart
        And seetext '@empty_cart_msg'
        And set cart_filled to false

    @app
    Scenario: extend menu
        Given screen is app_qvc_menuclosed
        When click More
        Then see Manage Reminders
        And click Legal

    @bridge
    Scenario: continue
        Given screen is shipping
        When click CONTINUE
        And click !textcontains:'1 payment of'
        And click CONTINUE
        Then screen is payment
