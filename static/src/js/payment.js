/*if ($(location).attr('pathname') == "/shop/payment"){
    var buttonP = $(".float-right.mt-2");
    var buttonD = $(".card-body.o_payment_option_card");
    buttonP.insertAfter(buttonD);
}*/

odoo.define('payment_billpocket.payments', function (require) {
    'use strict';
    
    var publicWidget = require('web.public.widget');

    publicWidget.registry.ShowPayment = publicWidget.Widget.extend({
        selector: '#payment_method',
        events: {
            "click  [name='o_payment_option_card']": "_CRadioPayment",
        },
        _CRadioPayment: function (ev){
            var buttonD = ev.target;
            var buttonP = $(".float-right.mt-2")
            $(".btn.btn-primary").addClass("float-right m-2");
            buttonP.insertAfter(buttonD);
        }
    });
    
    return publicWidget.registry.ShowPayment;    
});

