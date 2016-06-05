var mem_usedp = 0;
var cpu_usedp = 0;
var is_running = true;

function processMemData(data)
{
    if(is_running)
    {
	    mem_usedp = data.monitor.mem_use.usedp;
	    var usedp = data.monitor.mem_use.usedp;
	    var unit = data.monitor.mem_use.unit;
	    var quota = data.monitor.mem_use.quota.memory/1024.0;
	    var val = data.monitor.mem_use.val;
	    var out = "("+val+unit+"/"+quota.toFixed(2)+"MiB)";
	    $("#con_mem").html((usedp/0.01).toFixed(2)+"%<br/>"+out);
    }
    else
    {
        mem_usedp = 0;
        $("#con_mem").html("--");
    }
}
function getMemY()
{
	return mem_usedp*100;
}
function processCpuData(data)
{
    if(is_running)
    {
	    cpu_usedp = data.monitor.cpu_use.usedp;
	    var val = data.monitor.cpu_use.val;
	    var unit = data.monitor.cpu_use.unit;
        var quota = data.monitor.cpu_use.quota.cpu;
        var quotaout = "("+quota;
        if(quota == 1)
            quotaout += " Core)";
        else
            quotaout += " Cores)";
	    $("#con_cpu").html(val +" "+ unit+"<br/>"+quotaout);
    }
    else
    {
        cpu_usedp = 0;
        $("#con_cpu").html("--");
    }
}
function getCpuY()
{
	return cpu_usedp*100;
}

function plot_graph(container,url,processData,getY) {

    //var container = $("#flot-line-chart-moving");

    // Determine how many data points to keep based on the placeholder's initial size;
    // this gives us a nice high-res plot while avoiding more than one point per pixel.

    var maximum = container.outerWidth() / 2 || 300;

    //

    var data = [];



    function getBaseData() {

        while (data.length < maximum) {
           data.push(0)
        }

        // zip the generated y values with the x values

        var res = [];
        for (var i = 0; i < data.length; ++i) {
            res.push([i, data[i]])
        }

        return res;
    }

    function getData() {

        if (data.length) {
            data = data.slice(1);
        }

        if (data.length < maximum) {
            $.post(url,{user:"root",key:"root"},processData,"json");
	    var y = getY();
            data.push(y < 0 ? 0 : y > 100 ? 100 : y);
        }

        // zip the generated y values with the x values

        var res = [];
        for (var i = 0; i < data.length; ++i) {
            res.push([i, data[i]])
        }

        return res;
    }



    series = [{
        data: getBaseData(),
        lines: {
            fill: true
        }
    }];


    var plot = $.plot(container, series, {
        grid: {

            color: "#999999",
            tickColor: "#D4D4D4",
            borderWidth:0,
            minBorderMargin: 20,
            labelMargin: 10,
            backgroundColor: {
                colors: ["#ffffff", "#ffffff"]
            },
            margin: {
                top: 8,
                bottom: 20,
                left: 20
            },
            markings: function(axes) {
                var markings = [];
                var xaxis = axes.xaxis;
                for (var x = Math.floor(xaxis.min); x < xaxis.max; x += xaxis.tickSize * 2) {
                    markings.push({
                        xaxis: {
                            from: x,
                            to: x + xaxis.tickSize
                        },
                        color: "#fff"
                    });
                }
                return markings;
            }
        },
        colors: ["#1ab394"],
        xaxis: {
            tickFormatter: function() {
                return "";
            }
        },
        yaxis: {
            min: 0,
            max: 110
        },
        legend: {
            show: true
        }
    });

    // Update the random dataset at 25FPS for a smoothly-animating chart

    setInterval(function updateRandom() {
        series[0].data = getData();
        plot.setData(series);
        plot.draw();
    }, 1000);

}


var host = window.location.host;

var node_name = $("#node_name").html();
var url = "http://" + host + "/monitor/vnodes/" + node_name;

function processDiskData()
{
    $.post(url+"/disk_use/",{},function(data){
        var diskuse = data.monitor.disk_use;
        var usedp = diskuse.percent;
        var total = diskuse.total/1024.0/1024.0;
        var used = diskuse.used/1024.0/1024.0;
        var detail = "("+used.toFixed(2)+"MiB/"+total.toFixed(2)+"MiB)";
        $("#con_disk").html(usedp+"%<br/>"+detail);
    },"json");
}
setInterval(processDiskData,1000);

function processBasicInfo()
{
    $.post(url+"/basic_info/",{},function(data){
        basic_info = data.monitor.basic_info;
        state = basic_info.State;
        if(state == 'STOPPED')
        {
            is_running = false;
            $("#con_state").html("<div class='label label-danger'>Stopped</div>");
            $("#con_ip").html("--");
        }
        else
        {
            is_running = true;
            $("#con_state").html("<div class='label label-primary'>Running</div>");
            $("#con_ip").html(basic_info.IP);
        }
        $("#con_time").html(basic_info.RunningTime+"s");
    },"json");
}
setInterval(processBasicInfo,1000);
plot_graph($("#mem-chart"),url + "/mem_use/",processMemData,getMemY);
plot_graph($("#cpu-chart"),url + "/cpu_use/",processCpuData,getCpuY);
