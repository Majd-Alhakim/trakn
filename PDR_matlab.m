function PDR_matlab
% PDR system with SVR stride estimation using log-binned histogram features

%% User Settings
port         = "COM4";
baud         = 115200;
win_step     = 0.40;       % Window size for step detection (seconds)
min_step_dt  = 0.35;       % Minimum time between steps (prevents double-counting)
p_wein       = 0.25;       % Weinberg exponent
K_wein       = 0.47;       % Weinberg coefficient (calibrated for our setup)
min_stride   = 0.25;       % Minimum realistic stride length (m)
max_stride   = 1.40;       % Maximum realistic stride length (m)
gyro_to_rad  = 1;          % Gyro already in rad/s from Arduino
cal_time     = 2;          % Gyro bias calibration time at startup (seconds)

%% Log Histogram Bin Setup
% These parameters define how we extract features from acceleration data
amax = 20;         % Max acceleration magnitude we expect
Kbin = 0.117;      % Controls bin spacing in log scale
Ml = 10;           % Number of bins below gravity
Mh = 10;           % Number of bins above gravity
M = Ml + Mh;       % Total number of bins (20)

% Create bin edges (logarithmic spacing)
E = zeros(M+1,1);
E(1) = 0;
for i = 2:M+1
    if i <= Ml+1
        % Bins below gravity are log-spaced
        E(i) = 9.8 * (0.5*Kbin)^((Ml + 1 - i)/Ml);
    else
        % Bins above gravity are linearly spaced
        E(i) = 9.8 + (amax-9.8)*(i-Ml-1)/Mh;
    end
end

%% Load SVR Model (if it exists)
use_ml = false;
if exist('stride_svr.mat','file')
    load('stride_svr.mat','mdl','X_all','y_all');
    use_ml = true;
    disp('Loaded existing SVR model from file.');
else
    X_all = [];
    y_all = [];
    disp('No model found. Using Weinberg formula only.');
end

%% Serial Port Setup
delete(instrfindall);  % Clear any old serial connections
s = serialport(port, baud);
configureTerminator(s,"CR/LF");
flush(s);

%% State Variables
pkt_count = 0;
step_count = 0;
last_step_t = -inf;
X = 0; Y = 0;              % Position in 2D
heading = 0;               % Current heading angle
t0 = tic;
last_t = 0;

% Filtered values
a_mag_f = [];
gz_f = [];

% Rolling buffer for step detection
buf_t = [];
buf_a = [];

% Path tracking
path = [X Y];
stride_pred = [];
step_times  = [];
step_features = [];

% Gyro bias calibration variables
bias_collect = true;
bias_count = 0;
gyro_sum = 0;
gyro_bias = 0;

%% Setup Plot Window
f = figure('Name','PDR with SVR Stride Estimation','Color','k');
ax1 = axes(f);
hold(ax1,'on');
grid(ax1,'on');
axis equal;
xlabel(ax1,'X (m)','Color','w');
ylabel(ax1,'Y (m)','Color','w');
title(ax1,'Real-Time Position Tracking','Color','w');

% Plot handles
hP = plot(ax1,X,Y,'w-','LineWidth',2);          % Path line
hS = plot(ax1,X,Y,'ro','MarkerSize',9,'LineWidth',2);  % Current position marker

% Status text
txt = text(ax1,0.01,0.95,'','Units','normalized','Color',[1 1 0],...
    'FontSize',11,'VerticalAlignment','top','Interpreter','none');

% Dark theme
set(ax1,'Color','k','XColor',[.85 .85 .85],'YColor',[.85 .85 .85]);

%% Main Loop - Process IMU Data
while ishghandle(f)
    % Read data from Arduino
    line="";
    try
        line = readline(s);
    catch
        drawnow;
        continue;
    end

    if ~isstring(line) && ~ischar(line), continue; end
    line = strtrim(string(line));
    if strlength(line)==0 || count(line,"Accel")<1, continue; end

    % Parse JSON packet
    try
        pkt = jsondecode(line);
        axx = double(pkt.AccelX);
        ayy = double(pkt.AccelY);
        azz = double(pkt.AccelZ);
        gz = double(pkt.GyroZ);
    catch
        continue;
    end

    t = toc(t0);
    dt = max(1e-3, t - last_t);
    last_t = t;

    % ---- Gyro Bias Calibration (runs during first 2 seconds) ----
    if bias_collect
        gyro_sum = gyro_sum + gz;
        bias_count = bias_count + 1;
        if t > cal_time
            gyro_bias = gyro_sum / bias_count;
            bias_collect = false;
            fprintf('Gyro bias calibrated: %.6f rad/s (from %d samples)\n', gyro_bias, bias_count);
        end
    end

    % Apply bias correction
    if ~bias_collect
        gz_corrected = gz - gyro_bias;
    else
        gz_corrected = 0;  % Don't integrate during calibration
    end

    % ---- Signal Filtering (exponential moving average) ----
    a_mag = sqrt(axx^2 + ayy^2 + azz^2);
    alpha = 1 - exp(-2*pi*3.2*dt);  % Filter coefficient

    if isempty(a_mag_f), a_mag_f = a_mag; end
    a_mag_f = a_mag_f + alpha*(a_mag - a_mag_f);

    if isempty(gz_f), gz_f = gz_corrected; end
    gz_f = gz_f + alpha*(gz_corrected - gz_f);

    % Update heading by integrating gyro
    heading = heading + gz_f*dt*gyro_to_rad;

    % Add to rolling buffer for step detection
    buf_t = [buf_t t];
    buf_a = [buf_a a_mag_f];

    % Keep only recent data in buffer
    keep = buf_t >= t - win_step;
    buf_t = buf_t(keep);
    buf_a = buf_a(keep);

    % ---- False Step Suppression ----
    % Check if device is stationary (low variation in acceleration)
    stationary_activity = std(buf_a) < 1.2;
    near_gravity = abs(mean(buf_a) - 9.8) < 0.4;

    pkt_count = pkt_count + 1;

    % Only check for steps every other packet (reduces computation)
    if mod(pkt_count, 2) == 0
        % Skip step detection if device seems stationary
        if stationary_activity || near_gravity
            continue;
        end

        dt_step = t - last_step_t;
        a_max = max(buf_a);
        a_min = min(buf_a);
        swing = a_max - a_min;

        % Adaptive thresholds based on current data
        th_peak_adapt  = median(buf_a) + 2*std(buf_a);
        th_swing_adapt = 0.9*std(buf_a);

        % Check if this is a valid step
        is_valid = (dt_step > min_step_dt) && ...
            (a_max > th_peak_adapt) && ...
            (swing > th_swing_adapt);

        if is_valid
            step_count = step_count + 1;
            last_step_t = t;

            % === Extract histogram features from acceleration data ===
            hcounts = histcounts(buf_a, E);
            hfeat = hcounts / sum(hcounts);  % Normalize to probabilities

            % === Estimate stride length ===
            % Weinberg baseline
            wein = K_wein * swing^p_wein;

            % If we have a trained model, use hybrid approach
            if use_ml
                stride_ml = predict(mdl, hfeat);
                stride_ml = max(0.45, min(0.9, stride_ml));  % Clamp ML prediction
                stride = 0.5*wein + 0.5*stride_ml;  % 50-50 hybrid
            else
                stride = wein;  % Just use Weinberg
            end

            % Clamp to realistic range
            stride = max(min_stride, min(max_stride, stride));

            % Store for later analysis
            stride_pred = [stride_pred; stride];
            step_times = [step_times; t];
            step_features = [step_features; hfeat];

            % Update 2D position
            X = X + stride*cos(heading);
            Y = Y + stride*sin(heading);
            path = [path; X Y];
        end
    end

    % Update plot
    set(hP, 'XData', path(:,1), 'YData', path(:,2));
    set(hS, 'XData', path(end,1), 'YData', path(end,2));

    total_dist = sum(stride_pred);
    set(txt, 'String', sprintf('Steps: %d | Distance: %.2f m | Heading: %.1f°', ...
        step_count, total_dist, rad2deg(heading)));

    % Auto-scale axes to fit path
    xlim(ax1, [min(path(:,1))-2, max(path(:,1))+2]);
    ylim(ax1, [min(path(:,2))-2, max(path(:,2))+2]);

    drawnow limitrate;
end

%% After Walking - Option to Retrain Model
fprintf('\nFinal Stats:\n');
fprintf('Distance: %.2f m | Heading: %.1f° | Steps: %d\n', ...
    total_dist, rad2deg(heading), step_count);

choice = lower(input('Save this walk and retrain model? (y/n): ','s'));
if strcmp(choice,'y')
    D_true = input('Enter the actual distance you walked (meters): ');

    N = size(step_features, 1);
    stride_true = D_true / N;  % Average stride for this walk
    y_new = stride_true * ones(N,1);

    % Add to training dataset
    X_all = [X_all; step_features];
    y_all = [y_all; y_new];

    % Remove any invalid data
    mask = all(isfinite(X_all), 2);
    X_all = X_all(mask, :);
    y_all = y_all(mask);

    % Retrain SVR model
    mdl = fitrsvm(X_all, y_all, 'KernelFunction', 'gaussian', ...
        'Standardize', true, 'KernelScale', 'auto');

    % Save updated model
    save('stride_svr.mat', 'mdl', 'X_all', 'y_all');
    fprintf('Model updated! Now have %d training steps.\n', numel(y_all));

    % Show distribution of training data
    figure;
    histogram(y_all);
    xlabel('Stride Length (m)');
    ylabel('Count');
    title('Training Data Distribution');
else
    fprintf('Model not updated.\n');
end

% Clean up serial connection
try
    clear s;
end

end



