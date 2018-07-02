Feature: zappos
    @app
    Scenario: skip type choosing interface
        Given screen is app_zappos_choosecat
        Then click !marked:'Shoes'
        And click !marked:'Sandals'
        And click !marked:'APPLY FILTERS'+110+0

    @app
    Scenario: select option
        Given screen is app_zappos_option
        Then click !marked:'Select a size'
        And click !textcontains:'Little Kid'
        #click !marked:'ADD to CART'

