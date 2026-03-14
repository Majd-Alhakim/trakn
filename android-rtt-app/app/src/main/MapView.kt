// =============================================================================
// TRAKN Android RTT App — MapView.kt
// Floor plan canvas + grid points overlay + live distance display.
// PRD Reference: TRAKN_PRD.md Section 9
// =============================================================================

package org.trakn.rttapp

import android.content.Context
import android.graphics.*
import android.net.Uri
import android.view.MotionEvent
import android.view.View
import android.widget.Toast

class MapView(context: Context) : View(context) {

    // -------------------------------------------------------------------------
    // Data
    // -------------------------------------------------------------------------
    private var floorBitmap: Bitmap? = null
    private var scalePxPerMetre: Float = 50f    // default; overridden on scale set

    data class GridPointOverlay(
        val xM: Float,    // metres
        val yM: Float,
        val isWalkable: Boolean,
        var distancesToAps: Map<String, Float> = emptyMap()
    )

    private val gridPoints     = mutableListOf<GridPointOverlay>()
    private var selectedPoint: GridPointOverlay? = null
    private var touchX = 0f; private var touchY = 0f

    // -------------------------------------------------------------------------
    // Paints
    // -------------------------------------------------------------------------
    private val paintWalkable = Paint().apply {
        color = Color.argb(160, 80, 200, 255); style = Paint.Style.FILL
    }
    private val paintBlocked = Paint().apply {
        color = Color.argb(160, 255, 80, 80); style = Paint.Style.FILL
    }
    private val paintSelected = Paint().apply {
        color = Color.YELLOW; style = Paint.Style.STROKE; strokeWidth = 3f
    }
    private val paintLabel = Paint().apply {
        color = Color.WHITE; textSize = 28f; isAntiAlias = true
    }
    private val paintCircle = Paint().apply {
        color = Color.argb(200, 255, 200, 50); style = Paint.Style.FILL
    }

    // -------------------------------------------------------------------------
    // onDraw
    // -------------------------------------------------------------------------
    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)

        // Background
        canvas.drawColor(Color.rgb(15, 17, 23))

        // Floor plan
        floorBitmap?.let { bmp ->
            val destRect = RectF(0f, 0f, width.toFloat(), height.toFloat())
            canvas.drawBitmap(bmp, null, destRect, null)
        }

        // Grid points
        for (gp in gridPoints) {
            val px = gp.xM * scalePxPerMetre
            val py = gp.yM * scalePxPerMetre
            val paint = if (gp.isWalkable) paintWalkable else paintBlocked
            canvas.drawCircle(px, py, 5f, paint)
        }

        // Selected point
        selectedPoint?.let { gp ->
            val px = gp.xM * scalePxPerMetre
            val py = gp.yM * scalePxPerMetre
            canvas.drawCircle(px, py, 12f, paintSelected)

            // Distance labels
            var yOff = 0f
            for ((bssid, dist) in gp.distancesToAps) {
                canvas.drawText("${bssid.takeLast(5)}: ${String.format("%.2f", dist)}m",
                    px + 14f, py + yOff, paintLabel)
                yOff += 32f
            }
        }

        // Touch cross-hair
        if (touchX > 0 || touchY > 0) {
            canvas.drawCircle(touchX, touchY, 8f, paintCircle)
        }
    }

    // -------------------------------------------------------------------------
    // Touch: select nearest grid point
    // -------------------------------------------------------------------------
    override fun onTouchEvent(event: MotionEvent): Boolean {
        if (event.action == MotionEvent.ACTION_DOWN || event.action == MotionEvent.ACTION_MOVE) {
            touchX = event.x; touchY = event.y
            selectedPoint = nearestGridPoint(event.x / scalePxPerMetre, event.y / scalePxPerMetre)
            invalidate()
        }
        return true
    }

    private fun nearestGridPoint(xM: Float, yM: Float): GridPointOverlay? {
        return gridPoints.minByOrNull {
            val dx = it.xM - xM; val dy = it.yM - yM
            dx*dx + dy*dy
        }
    }

    // -------------------------------------------------------------------------
    // Public API
    // -------------------------------------------------------------------------

    fun setFloorPlan(bitmap: Bitmap) {
        floorBitmap = bitmap
        invalidate()
    }

    fun setGridPoints(points: List<GridPointOverlay>) {
        gridPoints.clear()
        gridPoints.addAll(points)
        invalidate()
    }

    fun updateDistances(distances: Map<String, Float>) {
        selectedPoint?.distancesToAps = distances
        invalidate()
    }

    fun setScale(pxPerMetre: Float) {
        scalePxPerMetre = pxPerMetre
        invalidate()
    }

    fun promptLoadFloorPlan() {
        // In a real app this would launch an image picker intent.
        // The Activity handles the result and calls setFloorPlan().
        Toast.makeText(context, "Select a floor plan image from the gallery.", Toast.LENGTH_SHORT).show()
    }
}
