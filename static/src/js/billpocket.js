if ($(location).attr('pathname') == "/shop/payment" || $(location).attr('pathname') == "/shop/checkout"){
    $(".btn.btn-primary.float-right").addClass("d-none")
}

/*(function($){
    var maxFront = 1;
    var maxBack = 4;
    var lastLength = -1;
    $('#card').on('keydown', function(){
      var self = this;
      setTimeout(function(){
         var val = $(self).val();
          var xxx = '';
          if(val.length > lastLength){
            if($(self).data('value') == undefined){
                $(self).data('value',  val[val.length-1]);
            }
            else{
                $(self).data('value',  $(self).data('value') + val[val.length-1]);
            }
            
          }else{
            var $value = $(self).data('value');
            $(self).data('value', $value.slice(0, $value.length-(lastLength-val.length)));
          }
  
          val = $(self).data('value');
          if(val != undefined)
          {
            fr = val.slice(0,maxFront);
            bk = val.slice(-maxBack);
            if (val.length > maxFront+maxBack-1) {
            for (var i = maxFront; i < val.length-maxBack; i++) {
                xxx = xxx + 'X';
            }
            $(self).val( fr + xxx + bk);
            }else{
            $(self).val(val)
            }
            lastLength = val.length;
            $('#term').val($(self).data('value'));
          }
        });
    });
  })(jQuery);
*/

odoo.define('payment_billpocket.master_payments', function (require) {
    'use strict';
    
    var publicWidget = require('web.public.widget');
    
    publicWidget.registry.ShowCard = publicWidget.Widget.extend({
        selector: '.checkout_autoformat',
        events: {
            "click input[name='submit']": "_onGif",
            "click .eyeeCvv": "_onCvv",
            "click .eyeeCard": "_onCard",
            "keypress input[name='expire']": "_onExpire",
        },
        init: function(){
            this._checkType();
        },
        _onExpire: function (ev){
            var expire = $("#expire").val()
            if(expire.length == 2)
            {
                $("#expire").val( $("#expire").val() + "/")
            }
        },
        _onGif: function (){
            $(".o_loader").removeClass('d-none')
        },
        _onCvv: function (){
            var cvv = $("#cvv")
            if (cvv.hasClass("smi"))
            {
                cvv.removeClass("smi")
            }
            else{
                cvv.addClass("smi")
            }
        },
        _onCard: function (){
            var cvv = $("#card")
            if (cvv.hasClass("smi"))
            {
                cvv.removeClass("smi")
            }
            else{
                cvv.addClass("smi")
            }
        },
        _checkType: function () {
            var card = $("#card").val()
            var select = document.getElementById('card_type');
            if(card != ""){
                //visa
                if(card[0] == '4'){ select[1].selected = 1; }
                //mc
                if(card[0] == '5'){ select[2].selected = 1; }
                //amex
                if(card[0] == '3'){ select[3].selected = 1; }
                //other
                if(!(['3', '4', '5'].includes(card[0]) )){ select[0].selected = 1; }
            }
        }
    });
    
    return publicWidget.registry.ShowCard;    
});