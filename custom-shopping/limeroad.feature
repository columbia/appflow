Feature: limeroad
    @app
    Scenario: pick male
        Given screen is intro
        Then click !marked:'men_tv'

    @override
    @bridge
    Scenario: fill in address [india]
        Given screen is addredit
        And addr_addr_filled is false
        And addr_name_filled is true
        When text edit_pincode '560016'
        And text edit_address_1 'No.3'
        And text edit_address_2 'Old Madras Rd'
        #And click spinner_address_type
        And click Home
        Then set addr_addr_filled to true
        And screen is addredit

    @bridge
    Scenario: show card edit
        Given screen is addredit
        And addr_addr_filled is true
        And addr_name_filled is true
        And addr_phone_filled is true
        When scroll down
        And click Credit Card
        Then screen is cardedit

    @app
    Scenario: pass intro
        Given screen is app_limeroad_intro
        When click men_layout
        And click Watches
        And click !textcontains:'+'
        And wait 5
        Then screen is main

    @override
    Scenario: change count [with buttons]
        Given screen is cart
        And cart_filled is true
        Then seein @item_count '1'
        And click plus_iv
        And seein @item_count '2'
        And click minus_iv
        And seein @item_count '1'
        And screen is cart
