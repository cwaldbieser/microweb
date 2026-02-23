{% args firmware, uptime, rssi, ip_addr, hysteresis, alarm_temperature, delay, correction %}
<!DOCTYPE html>
<html>
<head>
    <title>SmartStat - Settings</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="stylesheet" type="text/css" href="style.css">
</head>
<body>
    <div class="container">
        <header>
            <a href="../" class="nav-btn">← Back</a>
            <h1>System Info</h1>
        </header>

        <table>
            <tr>
                <th>Parameter</th>
                <th>Value</th>
            </tr>
            <tr>
                <td>Firmware</td>
                <td>{{firmware}}</td>
            </tr>
            <tr>
                <td>Uptime seconds</td>
                <td>{{uptime}}</td>
            </tr>
            <tr>
                <td>WiFi Strength</td>
                <td>{{rssi}} dBm</td>
            </tr>
            <tr>
                <td>IP Address</td>
                <td>{{ip_addr}}</td>
            </tr>
            <tr>
                <td>Hysteresis</td>
                <td>{{hysteresis}}°C</td>
            </tr>
            <tr>
                <td>Alarm Temperature</td>
                <td>{{alarm_temperature}}°C</td>
            </tr>
            <tr>
                <td>Delay</td>
                <td>{{delay}}°C</td>
            </tr>
            <tr>
                <td>Correction Temperature</td>
                <td>{{correction}}°C</td>
            </tr>
        </table>
        
        <div style="margin-top: 20px;">
            <form action="/reboot" method="POST">
                <button class="btn btn-danger">Reboot Device</button>
            </form>
        </div>
    </div>
</body>
</html>

