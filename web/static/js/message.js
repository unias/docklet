$("#talk").click(function(){
    //点击时图标隐藏
    $(this).hide();
    //聊天框显示，接口在这获取聊天信息
    $("#talk_box").animate({"right":"0px","opacity":"1"});
})

$("#talk_exc").click(function(){
    //点击叉号关闭
    $("#talk_box").animate({"right":"-350px","opacity":"0"},function(){
        $("#talk").show();
    });
})

$("#talk_back").click(function(){
    getMessageList()
    //点击返回聊天框隐藏
    $(this).hide();
    $("#talk_content").hide();
    $("#title").text("消息列表");
    $("#talk_component").hide();
    //好友显示，接口在这获取信息
    $("#talk_contacts").show();
})

url = 'http://localhost:8000/'

if (document.getElementById("talk_back")) {
    getMessageList()
    //点击返回聊天框隐藏
    $("#talk_back").hide();
    $("#talk_content").hide();
    $("#title").text("消息列表");
    $("#talk_component").hide();
    //好友显示，接口在这获取信息
    $("#talk_contacts").show();
}

$.fn.scrollBottom = function(scroll){
  if(typeof scroll === 'number'){
    window.scrollTo(0,$(document).height() - $(window).height() - scroll);
    return $(document).height() - $(window).height() - scroll;
  } else {
    return $(document).height() - $(window).height() - $(window).scrollTop();
  }
}

function getMessageList() {
    // console.log('getMessageList begin')
    if (document.getElementById("talk_back")) {
        $.ajax({
            type:'post',
            url:url + 'message/queryList/',
            dataType: "json",
            success:function(data) {
                // console.log(data);

                var str = ''
                for (var i = 0; i < data.data.length; ++i) {
                    // console.log(data.data[i].last_message)
                    var now = data.data[i]
                    str += '<div class="contacts_list" id = ' + now.to_person_id + ' name = ' + now.to_person_name + '>'
                    str += '<div class="contacts_portrait"></div>'
                    str += '<p class="contacts_name">' + now.to_person_name + '   <span class="contacts_time">' + now.last_message_date.substring(0, 16) + '</span></p>'
                    str += '<p class="contacts_text">' + now.last_message + ' </p>'
                    str += '</div>'
                }
                $("#talk_contacts_box").html(str)

                $('.contacts_list').each(function () {
                    $(this).click(function() {
                        selected_id = $(this).attr("id")
                        $("#talk_back").show();
                        $("#talk_content").show();
                        $("#title").text($(this).attr("name"));
                        $("#talk_component").show();
                        $("#talk_contacts").hide();
                        $("#talk_component").show();
                        getMessages(true)
                        console.log($(this).attr("id") + ' clicked ')
                    })
                })

            },
            error: function (xhr, type) {
                console.log("数据不能加载！")
            }
        })
    }
}

function getMessages(scrollToBottom) {
    $.ajax(
        {
            type:'post',
            url:url + 'message/query/',
            dataType: "json",
            data: {
                user_id: selected_id
            },
            success:function(data) {
                // console.log(data);
                var str = ''
                for (var i = 0; i < data.data.length; ++i) {
                    // console.log(data.data[i].type)
                    var now = data.data[i]
                    if ((now.from_user == 'question') ^ (data.query_id != now.from_user))
                        str += '<li class="talk_other">'
                    else
                        str += '<li class="talk_own">'
                    str += '<p class="talk_name">' + now.from_user_name + '</p>'
                    // str += '<p class="talk_name">' + now.from_user + '<span class="talk_time">' + now.date + '</span></p>'
                    str += '<p class="talk_text">' + now.content + '</p>'
                    str += '</li>'
                }
                $("#talk_content_box").html(str)
                if (scrollToBottom) {
                    $("#talk_content_box").scrollTop(99999)
                }
            },
            error: function (xhr, type) {
                console.log("数据不能加载！")
            }
        }
    )
}

var selected_id = 2

function sendMessage() {
    var content = $('#talk_txt').val();
    $.ajax(
        {
            type:'post',
            url:url + 'message/create/',
            dataType: "json",
            data: {
                content:content,
                to_user:selected_id
            },
            success:function(data){
                // console.log(data);
                getMessages(true);
            }
        }
    )
}

function strlen(str){
    var len = 0;
    for (var i=0; i<str.length; i++) {
        var c = str.charCodeAt(i);
        //单字节加1
        if ((c >= 0x0001 && c <= 0x007e) || (0xff60<=c && c<=0xff9f)) {
            len++;
        }
        else {
            len+=2;
        }
    }
    return len;
}

$('#talk_send').click(function(){
    if(strlen($('#talk_txt').val())<=250){
        if($.trim($('#talk_txt').val())!= '' ){
            sendMessage();
            $('#talk_txt').val('');
        }else{
        }
    }else{
    }

});

getMessages(true);
getMessageList();

setInterval(function(){
    // console.log('refreshing..')
    getMessages(false);
    getMessageList();
},1000);
