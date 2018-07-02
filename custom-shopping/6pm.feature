Feature: 6pm
    @app
    Scenario: skip type choosing interface
        Given screen is app_6pm_choosecat
        When wait 6
        And click !marked:'menu_filter'
        And click !marked:'Shoes'
        And click !marked:'menu_filter'
        And click !marked:'Sandals'

    @app
    Scenario: select option
        Given screen is app_6pm_option
        When click !marked:'Select a size'
        #click !textcontains:'Little Kid'
        And click !textcontains:'31/32'
        #And click !marked:'Add to bag'
