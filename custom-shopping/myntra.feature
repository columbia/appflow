Feature: myntra
    #    Scenario: select email
    #        Given screen is sys_myntra_signupmethod
    #        When click !marked:'btn_email_address'
    #        Then screen is register

    @app
    Scenario: give permission
        Given screen is app_myntra_permission
        Then click !marked:'Give Permission'

    @override
    @bridge
    Scenario: select and add
        Given screen is detail
        And cart_filled is false
        When click !marked:'ADD TO BAG'
        And click !marked:'L'
        And click !marked:'DONE'
        Then screen is detail
        And set cart_filled to true

    @override
    @bridge
    Scenario: fill in address [india]
        Given screen is addredit
        And addr_addr_filled is false
        And addr_name_filled is true
        When text pincode '560016'
        And click Choose
        And click Doorvaninagar
        And text address 'No.3 Old Madras Rd'
        And click Home
        Then screen is addredit
        And set addr_addr_filled to true

        #    Scenario: continue
        #        Given screen is address
        #        Then click CONTINUE
        #        And click Credit/Debit Card

    @app
    Scenario: ignore update msg
        Given screen is app_myntra_update
        Then scrollit sb__inner left

    @override
    Scenario: type in basic info [select email]
        Given screen is register
        When click btn_email_address
        And text @email '@username'
        Then screen is register

    @bridge
    Scenario: use right menu to account
        Given screen is main
        And loggedin is true
        When click !ImageView+no:'4'
        And click Account
        Then screen is account
