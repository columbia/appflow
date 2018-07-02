Feature: jabong
    @app
    Scenario: select option
        Given screen is app_jabong_option
        Then click !marked:'text_size_name_extra'

    @override
    @bridge
    Scenario: remove [through menu]
        Given screen is cart
        And cart_filled is true
        When click !id:'img_menu'
        And click !marked:'Remove'
        Then set cart_filled to false

    @override
    @bridge
    Scenario: fill in address [india]
        Given screen is addredit
        And addr_addr_filled is false
        And addr_name_filled is true
        When text edt_pincode '560016'
        And text edt_address 'No.3 Old Madras Rd'
        And click Select Locality
        And click Udaya Nagar
        Then screen is addredit
        And set addr_addr_filled to true

    @bridge
    Scenario: add card
        Given screen is checkout
        When click btn_confirm
        And click Credit Card
        Then screen is cardedit

    @override
    Scenario: change count [from menu]
        Given screen is cart
        And cart_filled is true
        Then seein @item_count '1'
        And click img_menu
        And click Change Quantity
        And click @item_count_2
        And seein @item_count '2'
        And click img_menu
        And click Change Quantity
        And click @item_count_1
        And seein @item_count '1'


