
var used = 0;
var total = 0;
var idle = 0;
var disk_usedp = 0;
var count = 0;
var Ki = 1024; 
var is_running = true;

function processMemData(data)
{
    if(is_running)
    {
	    used = data.monitor.meminfo.used;
	    total = data.monitor.meminfo.total;
	    var used2 = ((data.monitor.meminfo.used)/Ki).toFixed(2);
	    var total2 = ((data.monitor.meminfo.total)/Ki).toFixed(2);
	    var free2 = ((data.monitor.meminfo.free)/Ki).toFixed(2);	
	    $("#mem_used").html(used2);
	    $("#mem_total").html(total2);
	    $("#mem_free").html(free2);
    }
    else
    {
        total = 0;
	    $("#mem_used").html("--");
	    $("#mem_total").html("--");
	    $("#mem_free").html("--");
    }
}
function getMemY()
{
	if(total == 0)
		return 0;
	else 
		return (used/total)*100;
}
function processCpuData(data)
{
    if(is_running)
    {
	    idle = data.monitor.cpuinfo.idle;
	    var us = data.monitor.cpuinfo.user;
	    var sy = data.monitor.cpuinfo.system;
	    var wa = data.monitor.cpuinfo.iowait;
	    $("#cpu_user").html(us);
	    $("#cpu_system").html(sy);
	    $("#cpu_iowait").html(wa);
	    $("#cpu_idle").html(idle);
    }
    else
    {
        idle = 100;
	    $("#cpu_user").html("--");
	    $("#cpu_system").html("--");
	    $("#cpu_iowait").html("--");
	    $("#cpu_idle").html("--");
    }
}
function getCpuY()
{
	count++;
	//alert(idle);
	if(count <= 3 && idle <= 10)
		return 0;
	else
		return (100-idle);
}
function processDiskData(data)
{
	var vals = data.monitor.diskinfo;
	disk_usedp = vals[0].usedp;
	for(var idx = 0; idx < vals.length; ++idx)
	{
		var used = (vals[idx].used/Ki/Ki).toFixed(2);
		var total = (vals[idx].total/Ki/Ki).toFixed(2);
		var free = (vals[idx].free/Ki/Ki).toFixed(2);
		var usedp = (vals[idx].percent);
		var name = "#disk_" + (idx+1) + "_";
		$(name+"device").html(vals[idx].device);
		$(name+"used").html(used);
		$(name+"total").html(total);
		$(name+"free").html(free);
		$(name+"usedp").html(usedp);
	}
}
function getDiskY()
{
	return disk_usedp;
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
            $.post(url,{user:"root",key:"unias"},processData,"json");
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

var com_ip = $("#com_ip").html();
var url = "http://" + host + "/monitor/hosts/"+com_ip;

function processStatus()
{
    $.post(url+"/status/",{},function(data){
        var state = data.monitor.status;
        if(state == 'RUNNING')
            is_running = true;
        else
            is_running = false;
    },"json");
}
setInterval(processStatus,1000);

plot_graph($("#mem-chart"), url + "/meminfo/",processMemData,getMemY);
plot_graph($("#cpu-chart"), url +  "/cpuinfo/",processCpuData,getCpuY);
//plot_graph($("#disk-chart"), url + "/diskinfo",processDiskData,getDiskY);
$.post(url+"/diskinfo/",{},processDiskData,"json");

