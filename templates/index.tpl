{% args hostname, temp_c, temp_f, status, target_c, target_f %}
<!DOCTYPE html>
<html>
<head>
    <title>ThermoPy - Home</title>
    <meta charset="UTF-8">
    <meta http-equiv="refresh" content="60">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="stylesheet" type="text/css" href="style.css">
</head>
<body>
    <div class="container">
        <header>
            <h1>{{hostname}}</h1>
            <a href="settings" class="nav-btn">⚙ Settings</a>
        </header>

        <div class="temp-display">
            <div class="current-label">Current</div>
            <div class="temp-value">{{temp_c}}°C <span class="alt-units">({{temp_f}}℉)</span></div>
        </div>

        <div class="control-card">
            <h3>Target Temperature</h3>
            <form action="" method="GET" class="temp-controls-form">
                <div class="temp-controls">
                    <button name="adj" value="down" class="btn">-</button>
                    <span class="target-value">{{target_c}}°C <span class="alt-units2">({{target_f}}℉)</span></span>
                    <input type="hidden" name="target_temperature" value="{{target_c}}" />
                    <button name="adj" value="up" class="btn">+</button>
                </div>
                <div class="temp-controls">
                    <button type="submit" name="submit" value="submit" class="btn" style="width:50%;margin-right:2px;">Set</button>
                    <button name="reset" value="reset" class="btn" style="width:70%;margin-left:2px;">Refresh</button>
                </div>
            </form>
        </div>

        <div class="status-bar">
            <span>Status: <strong class="heating">{{status}}</strong></span>
        </div>

        <div style="margin-top: 20px;">
            <form action="/reboot" method="GET">
                <button class="btn btn-danger">Reboot Device</button>
            </form>
        </div>
    </div>
</body>
</html>

