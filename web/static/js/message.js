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
    //点击返回聊天框隐藏
    $(this).hide();
    $("#talk_content").hide();
    $("#title").text("好友列表");
    $("#talk_component").hide();
    //好友显示，接口在这获取信息
    $("#talk_contacts").show();
    $("#talk_component").hide();
})

url = 'http://localhost:8000/'

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
                    // console.log(data.data[i].type)
                    var now = data.data[i]
                    str += '<div class="contacts_list" id = ' + i + '>'
                    str += '<div class="contacts_portrait"></div>'
                    str += '<p class="contacts_name">' + now.to_person_name + '   <span class="contacts_time">' + now.last_message_date.substring(0, 16) + '</span></p>'
                    str += '<p class="contacts_text">something... </p>'
                    str += '</div>'
                }
                $("#talk_contacts_box").html(str)

                $('.contacts_list').each(function () {
                    $(this).click(function() {
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

function getMessages() {
    $.ajax(
        {
            type:'post',
            url:url + 'message/query/',
            dataType: "json",
            data: {
                user_id: 2
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
                console.log(data);
                getMessages();
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

getMessages();
getMessageList();

setInterval(function(){
    // console.log('refreshing..')
    getMessages();
    getMessageList();
},30000);
