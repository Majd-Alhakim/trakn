// =============================================================================
// TRAKN Parent App — lib/models/position.dart
// Position model matching the backend PositionResponseSchema.
// =============================================================================

class Position {
  final String mac;
  final double x;
  final double y;
  final double heading;
  final int stepCount;
  final double confidence;
  final DateTime ts;

  const Position({
    required this.mac,
    required this.x,
    required this.y,
    required this.heading,
    required this.stepCount,
    required this.confidence,
    required this.ts,
  });

  factory Position.fromJson(Map<String, dynamic> json) {
    return Position(
      mac:        json['mac']        as String,
      x:          (json['x']         as num).toDouble(),
      y:          (json['y']         as num).toDouble(),
      heading:    (json['heading']   as num).toDouble(),
      stepCount:  (json['step_count'] as num).toInt(),
      confidence: (json['confidence'] as num).toDouble(),
      ts:         DateTime.parse(json['ts'] as String),
    );
  }

  Map<String, dynamic> toJson() => {
    'mac':        mac,
    'x':          x,
    'y':          y,
    'heading':    heading,
    'step_count': stepCount,
    'confidence': confidence,
    'ts':         ts.toIso8601String(),
  };

  @override
  String toString() =>
      'Position(mac: $mac, x: ${x.toStringAsFixed(2)}, '
      'y: ${y.toStringAsFixed(2)}, heading: ${heading.toStringAsFixed(2)}, '
      'steps: $stepCount, conf: ${confidence.toStringAsFixed(3)})';
}
