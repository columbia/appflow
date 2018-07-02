Feature: filter

    @sort
    Scenario: sort by price increasing
        Given screen is sort
        When click @sort_pricelow
        Then screen is searchret
        And increasing @item_price

    @sort
    Scenario: sort by price decreasing
        Given screen is sort
        When click @sort_pricehigh
        Then screen is searchret
        And decreasing @item_price

    @sort
    Scenario: sort by review
        Given screen is sort
        When click @sort_review
        Then screen is searchret

    @sort
    Scenario: sort by recent
        Given screen is sort
        When click @sort_recent
        Then screen is searchret

    @sort
    Scenario: sort by popular
        Given screen is sort
        When click @sort_popular
        Then screen is searchret

    @sort
    Scenario: sort by price increasing [with confirm]
        Given screen is sort
        When click @sort_pricelow
        And click @apply
        Then screen is searchret
        And increasing @item_price

    @sort
    Scenario: sort by price decreasing [with confirm]
        Given screen is sort
        When click @sort_pricehigh
        And click @apply
        Then screen is searchret
        And decreasing @item_price

    @sort
    Scenario: sort by review [with confirm]
        Given screen is sort
        When click @sort_review
        And click @apply
        Then screen is searchret

    @sort
    Scenario: sort by recent [with confirm step]
        Given screen is sort
        When click @sort_recent
        And click @apply
        Then screen is searchret

    @sort
    Scenario: sort by popular [with confirm step]
        Given screen is sort
        When click @sort_popular
        And click @apply
        Then screen is searchret

    Scenario: filter by brand [with confirm step]
        Given screen is filter
        And filtered is false
        When click !textcontains:'@filter_brand'
        And click !textcontains:'@filter_brand_name'
        And click @filter_dialog_yes
        And click @apply
        Then screen is searchret
        And set filtered to true

    Scenario: filter by brand [no confirm step]
        Given screen is filter
        And filtered is false
        When click !textcontains:'@filter_brand'
        And click !textcontains:'@filter_brand_name'
        And click @apply
        Then screen is searchret
        And set filtered to true

    Scenario: filter by brand [no apply step]
        Given screen is filter
        And filtered is false
        When click !textcontains:'@filter_brand'
        And click !textcontains:'@filter_brand_name'
        Then screen is searchret
        And set filtered to true

    Scenario: filter by category [with confirm step]
        Given screen is filter
        And filtered is false
        When click !textcontains:'@filter_category'
        And click !textcontains:'@filter_category_name'
        And waitidle
        And click @filter_dialog_yes
        And click @apply
        Then screen is searchret
        And set filtered to true

    Scenario: filter by category [no confirm step]
        Given screen is filter
        And filtered is false
        When click !textcontains:'@filter_category'
        And click !textcontains:'@filter_category_name'
        And waitidle
        And click @apply
        Then screen is searchret
        And set filtered to true

    Scenario: filter by category [no apply step]
        Given screen is filter
        And filtered is false
        When click !textcontains:'@filter_category'
        And click !textcontains:'@filter_category_name'
        Then screen is searchret
        And set filtered to true

    Scenario: clear filter [with apply step]
        Given screen is searchret
        And filtered is true
        When click @filter
        And click @filter_reset
        And click @apply
        Then screen is searchret
        And set filtered to false

    Scenario: clear filter
        Given screen is searchret
        And filtered is true
        When click @filter
        And click @filter_reset
        Then screen is searchret
        And set filtered to false

    Scenario: filter by color [with confirm step]
        Given screen is filter
        And filtered is false
        When click !textcontains:'@filter_color'
        And click !textcontains:'@filter_color_name'
        And click @filter_dialog_yes
        And click @apply
        Then screen is searchret
        And set filtered to true

    Scenario: filter by color [no confirm step]
        Given screen is filter
        And filtered is false
        When click !textcontains:'@filter_color'
        And click !textcontains:'@filter_color_name'
        And click @apply
        Then screen is searchret
        And set filtered to true

    Scenario: filter by color [no apply step]
        Given screen is filter
        And filtered is false
        When click !textcontains:'@filter_color'
        And click !textcontains:'@filter_color_name'
        Then screen is searchret
        And set filtered to true

    Scenario: filter by price [with confirm step]
        Given screen is filter
        And filtered is false
        When click !textcontains:'@filter_price'
        And click !textcontains:'@filter_price_name'
        And click @filter_dialog_yes
        And click @apply
        Then screen is searchret
        And set filtered to true

    Scenario: filter by price [no confirm step]
        Given screen is filter
        And filtered is false
        When click !textcontains:'@filter_price'
        And click !textcontains:'@filter_price_name'
        And click @apply
        Then screen is searchret
        And set filtered to true

    Scenario: filter by price [no apply step]
        Given screen is filter
        And filtered is false
        When click !textcontains:'@filter_price'
        And click !textcontains:'@filter_price_name'
        Then screen is searchret
        And set filtered to true

    Scenario: filter by size [with confirm step]
        Given screen is filter
        And filtered is false
        When click !textcontains:'@filter_size'
        And click !textcontains:'@filter_size_name'
        And click @filter_dialog_yes
        And click @apply
        Then screen is searchret
        And set filtered to true

    Scenario: filter by size [no confirm step]
        Given screen is filter
        And filtered is false
        When click !textcontains:'@filter_size'
        And click !textcontains:'@filter_size_name'
        And click @apply
        Then screen is searchret
        And set filtered to true

    Scenario: filter by size [no apply step]
        Given screen is filter
        And filtered is false
        When click !textcontains:'@filter_size'
        And click !textcontains:'@filter_size_name'
        Then screen is searchret
        And set filtered to true

    @sortX
    Scenario: goto sort from filter
        Given screen is filter
        When click @sort
        Then screen is sort
