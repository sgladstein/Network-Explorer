package com.networkexplorer.survey

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Matrix
import android.graphics.Paint
import android.graphics.RectF
import android.view.MotionEvent
import android.view.ScaleGestureDetector
import android.view.View
import android.view.ViewConfiguration
import com.networkexplorer.survey.core.SignalScale
import kotlin.math.abs
import kotlin.math.hypot

/** A measured spot, in floor-plan fractions (0..1). */
data class SamplePoint(val x: Float, val y: Float, val rssi: Int?)

/**
 * Shows the floor plan, the spots measured so far (coloured by signal), and the spot the
 * user tapped. Pinch to zoom, drag to pan, tap to place the marker.
 */
class FloorPlanView(context: Context) : View(context) {
    private var bitmap: Bitmap? = null
    private var points: List<SamplePoint> = emptyList()
    var marker: Pair<Float, Float>? = null
        private set

    /** Called with the tapped position as fractions of the floor plan's width and height. */
    var onSpotSelected: ((Float, Float) -> Unit)? = null

    private val density = resources.displayMetrics.density
    private val baseMatrix = Matrix()
    private val userMatrix = Matrix()
    private val drawMatrix = Matrix()
    private val inverse = Matrix()
    private val imagePaint = Paint(Paint.FILTER_BITMAP_FLAG)
    private val dotPaint = Paint(Paint.ANTI_ALIAS_FLAG)
    private val ringPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE; strokeWidth = 2 * density; color = Color.WHITE
    }
    private val markerPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE; strokeWidth = 3 * density; color = Color.rgb(15, 108, 140)
    }
    private val textPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        textSize = 15 * density; textAlign = Paint.Align.CENTER; color = Color.GRAY
    }
    private var emptyText = "No floor plan yet"

    private val scaleDetector = ScaleGestureDetector(context, object : ScaleGestureDetector.SimpleOnScaleGestureListener() {
        override fun onScale(d: ScaleGestureDetector): Boolean {
            val current = FloatArray(9).also { userMatrix.getValues(it) }[Matrix.MSCALE_X]
            val factor = (current * d.scaleFactor).coerceIn(1f, 6f) / current
            userMatrix.postScale(factor, factor, d.focusX, d.focusY)
            invalidate()
            return true
        }
    })
    private val touchSlop = ViewConfiguration.get(context).scaledTouchSlop
    private var downX = 0f
    private var downY = 0f
    private var lastX = 0f
    private var lastY = 0f
    private var dragging = false
    private var multiTouch = false

    fun setFloorPlan(bmp: Bitmap?, emptyMessage: String = "No floor plan yet") {
        bitmap = bmp
        emptyText = emptyMessage
        marker = null
        userMatrix.reset()
        updateBaseMatrix()
        invalidate()
    }

    fun setPoints(list: List<SamplePoint>) {
        points = list
        invalidate()
    }

    fun clearMarker() {
        marker = null
        invalidate()
    }

    override fun onSizeChanged(w: Int, h: Int, oldw: Int, oldh: Int) = updateBaseMatrix()

    private fun updateBaseMatrix() {
        val b = bitmap ?: return
        if (width == 0 || height == 0) return
        baseMatrix.setRectToRect(
            RectF(0f, 0f, b.width.toFloat(), b.height.toFloat()),
            RectF(0f, 0f, width.toFloat(), height.toFloat()),
            Matrix.ScaleToFit.CENTER,
        )
    }

    override fun onDraw(canvas: Canvas) {
        val b = bitmap
        if (b == null) {
            canvas.drawText(emptyText, width / 2f, height / 2f, textPaint)
            return
        }
        drawMatrix.set(baseMatrix)
        drawMatrix.postConcat(userMatrix)
        canvas.drawBitmap(b, drawMatrix, imagePaint)

        val pt = FloatArray(2)
        val r = 7 * density
        for (p in points) {
            pt[0] = p.x * b.width; pt[1] = p.y * b.height
            drawMatrix.mapPoints(pt)
            dotPaint.color = SignalScale.colorFor(p.rssi)
            canvas.drawCircle(pt[0], pt[1], r, dotPaint)
            canvas.drawCircle(pt[0], pt[1], r, ringPaint)
        }
        marker?.let { (mx, my) ->
            pt[0] = mx * b.width; pt[1] = my * b.height
            drawMatrix.mapPoints(pt)
            canvas.drawCircle(pt[0], pt[1], 14 * density, markerPaint)
            canvas.drawLine(pt[0] - 20 * density, pt[1], pt[0] + 20 * density, pt[1], markerPaint)
            canvas.drawLine(pt[0], pt[1] - 20 * density, pt[0], pt[1] + 20 * density, markerPaint)
        }
    }

    override fun onTouchEvent(e: MotionEvent): Boolean {
        if (bitmap == null) return false
        scaleDetector.onTouchEvent(e)
        when (e.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                downX = e.x; downY = e.y; lastX = e.x; lastY = e.y
                dragging = false; multiTouch = false
                parent?.requestDisallowInterceptTouchEvent(true)
            }
            MotionEvent.ACTION_POINTER_DOWN -> multiTouch = true
            MotionEvent.ACTION_MOVE -> {
                if (!multiTouch && !scaleDetector.isInProgress) {
                    if (!dragging && hypot(e.x - downX, e.y - downY) > touchSlop) dragging = true
                    if (dragging) {
                        userMatrix.postTranslate(e.x - lastX, e.y - lastY)
                        invalidate()
                    }
                }
                lastX = e.x; lastY = e.y
            }
            MotionEvent.ACTION_UP -> {
                if (!dragging && !multiTouch && abs(e.x - downX) <= touchSlop && abs(e.y - downY) <= touchSlop) {
                    selectAt(e.x, e.y)
                    performClick()
                }
            }
        }
        return true
    }

    override fun performClick(): Boolean = super.performClick()

    private fun selectAt(x: Float, y: Float) {
        val b = bitmap ?: return
        drawMatrix.set(baseMatrix)
        drawMatrix.postConcat(userMatrix)
        if (!drawMatrix.invert(inverse)) return
        val pt = floatArrayOf(x, y)
        inverse.mapPoints(pt)
        val fx = pt[0] / b.width
        val fy = pt[1] / b.height
        if (fx !in 0f..1f || fy !in 0f..1f) return
        marker = fx to fy
        invalidate()
        onSpotSelected?.invoke(fx, fy)
    }
}
