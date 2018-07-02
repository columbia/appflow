Feature: googleexp

    @bridge
    Scenario: edit address
        Given screen is checkout
        When click Address Panel
        And click ADD NEW ADDRESS
        Then screen is addredit

    @bridge
    Scenario: edit card
        Given screen is checkout
        When click Payment Panel
        And click ADD NEW CARD
        Then screen is cardedit

    #    @override
    #    Scenario: remove [through menu]
    #        Given screen is cart
    #        And cart_filled is true
    #        When click More Options
    #        And click Clear cart
    #        And seetext '@empty_cart_msg'
    #        Then screen is cart
    #        And set cart_filled to false
    #
