from pathlib import Path
import sys
root=Path(sys.argv[1]); src=root/'app/src/main'; java=src/'java/com/pulse/health'
def change(path,old,new):
    s=path.read_text()
    if s.count(old)!=1: raise SystemExit('Could not match patch in '+str(path)+': '+old[:60])
    path.write_text(s.replace(old,new,1))
def put(rel,body):
    p=src/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(body.strip()+'\n')

gradle=root/'app/build.gradle.kts'
change(gradle,'implementation("androidx.health.connect:connect-client:1.1.0")','implementation("androidx.health.connect:connect-client:1.1.0")\n    implementation("androidx.work:work-runtime-ktx:2.10.1")')
change(gradle,'versionCode = 1','versionCode = 2')
change(gradle,'versionName = "1.0.0-source"','versionName = "1.1.0-beta"')
manifest=src/'AndroidManifest.xml'
change(manifest,'<uses-permission android:name="android.permission.health.READ_HEART_RATE" />','<uses-permission android:name="android.permission.health.READ_HEART_RATE" />\n    <uses-permission android:name="android.permission.health.READ_HEALTH_DATA_IN_BACKGROUND" />')
change(manifest,'android:label="Pulse"','android:label="Pulse"\n        android:icon="@mipmap/ic_launcher"\n        android:roundIcon="@mipmap/ic_launcher"')
put('res/values/icon_colors.xml','''<resources><color name="pulse_icon_background">#5441C8</color></resources>''')
put('res/drawable/ic_pulse_foreground.xml','''
<vector xmlns:android="http://schemas.android.com/apk/res/android" android:width="108dp" android:height="108dp" android:viewportWidth="108" android:viewportHeight="108">
  <path android:pathData="M27,54 L39,54 L45,39 L53,71 L61,35 L67,54 L81,54" android:strokeColor="#FFFFFFFF" android:strokeWidth="5.2" android:strokeLineCap="round" android:strokeLineJoin="round"/>
</vector>
''')
put('res/mipmap-anydpi-v26/ic_launcher.xml','''
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
  <background android:drawable="@color/pulse_icon_background"/>
  <foreground android:drawable="@drawable/ic_pulse_foreground"/>
</adaptive-icon>
''')
repo=java/'HealthConnectRepository.kt'
change(repo,'import androidx.health.connect.client.HealthConnectClient','import androidx.health.connect.client.HealthConnectClient\nimport androidx.health.connect.client.HealthConnectFeatures')
change(repo,'    private val client: HealthConnectClient get() = HealthConnectClient.getOrCreate(context)','''
    private val client: HealthConnectClient get() = HealthConnectClient.getOrCreate(context)
    val backgroundReadAvailable: Boolean get() = available && try {
        client.features.getFeatureStatus(
            HealthConnectFeatures.FEATURE_READ_HEALTH_DATA_IN_BACKGROUND
        ) == HealthConnectFeatures.FEATURE_STATUS_AVAILABLE
    } catch (_: Exception) { false }
    fun permissionForMetric(m: String): String? = when(m) {
        Metric.HEART -> HealthPermission.getReadPermission(HeartRateRecord::class)
        Metric.RESTING_HEART -> HealthPermission.getReadPermission(RestingHeartRateRecord::class)
        Metric.OXYGEN -> HealthPermission.getReadPermission(OxygenSaturationRecord::class)
        Metric.SLEEP -> HealthPermission.getReadPermission(SleepSessionRecord::class)
        Metric.STEPS -> HealthPermission.getReadPermission(StepsRecord::class)
        Metric.DISTANCE -> HealthPermission.getReadPermission(DistanceRecord::class)
        Metric.ACTIVE_CALORIES -> HealthPermission.getReadPermission(ActiveCaloriesBurnedRecord::class)
        Metric.TOTAL_CALORIES -> HealthPermission.getReadPermission(TotalCaloriesBurnedRecord::class)
        Metric.EXERCISE -> HealthPermission.getReadPermission(ExerciseSessionRecord::class)
        Metric.WEIGHT -> HealthPermission.getReadPermission(WeightRecord::class)
        Metric.BODY_FAT -> HealthPermission.getReadPermission(BodyFatRecord::class)
        else -> null
    }''')
put('java/com/pulse/health/PulseSyncScheduler.kt','''
package com.pulse.health
import android.content.Context
import androidx.health.connect.client.permission.HealthPermission
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import java.util.concurrent.TimeUnit

class PulseBackgroundWorker(context: Context, parameters: WorkerParameters) : CoroutineWorker(context, parameters) {
    override suspend fun doWork(): Result {
        val source = HealthConnectRepository(applicationContext)
        if (!source.backgroundReadAvailable) return Result.success()
        return try {
            val allowed = source.grantedPermissions()
            if (HealthPermission.PERMISSION_READ_HEALTH_DATA_IN_BACKGROUND !in allowed) {
                Result.success()
            } else {
                source.sync(HealthStore(applicationContext), 7)
                Result.success()
            }
        } catch (_: SecurityException) { Result.success() }
          catch (_: Exception) { Result.retry() }
    }
}
object PulseSyncScheduler {
    fun configure(context: Context, source: HealthConnectRepository, permissions: Set<String>) {
        val manager = WorkManager.getInstance(context.applicationContext)
        if (source.backgroundReadAvailable &&
            HealthPermission.PERMISSION_READ_HEALTH_DATA_IN_BACKGROUND in permissions) {
            manager.enqueueUniquePeriodicWork(
                "pulse-background-health-sync", ExistingPeriodicWorkPolicy.UPDATE,
                PeriodicWorkRequestBuilder<PulseBackgroundWorker>(30, TimeUnit.MINUTES).build()
            )
        } else manager.cancelUniqueWork("pulse-background-health-sync")
    }
}
''')
main=java/'MainActivity.kt'
change(main,'import androidx.core.content.FileProvider','import androidx.core.content.FileProvider\nimport androidx.lifecycle.Lifecycle\nimport androidx.lifecycle.LifecycleEventObserver\nimport androidx.health.connect.client.permission.HealthPermission')
change(main,'import kotlinx.coroutines.launch','import kotlinx.coroutines.launch\nimport kotlinx.coroutines.delay')
change(main,'                granted=source.grantedPermissions()\n                if(granted.isEmpty())','                granted=source.grantedPermissions()\n                PulseSyncScheduler.configure(context, source, granted)\n                if(granted.isEmpty())')
change(main,'    val openSamsung:()->Unit={','''
    val onBackgroundPermission:()->Unit={
        if (source.backgroundReadAvailable) {
            permissionsLauncher.launch(setOf(HealthPermission.PERMISSION_READ_HEALTH_DATA_IN_BACKGROUND))
        } else message="סנכרון ברקע לא נתמך במכשיר"
    }
    val openSamsung:()->Unit={''')
change(main,'    val exportLauncher=rememberLauncherForActivityResult(','''
    DisposableEffect(context) {
        val lifecycle=(context as? ComponentActivity)?.lifecycle
        val observer=LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) refreshPermissionsAndData()
        }
        lifecycle?.addObserver(observer)
        onDispose { lifecycle?.removeObserver(observer) }
    }
    LaunchedEffect(Unit) {
        while (true) {
            delay(180_000L)
            if ((context as? ComponentActivity)?.lifecycle?.currentState
                ?.isAtLeast(Lifecycle.State.RESUMED) == true) refreshPermissionsAndData()
        }
    }
    val exportLauncher=rememberLauncherForActivityResult(''')
change(main,'SyncScreen(store,source.available,granted,syncing,onPermissions,onSync,{page=it},openSamsung)',
    'SyncScreen(store,source.available,granted,syncing,onPermissions,onSync,{page=it},openSamsung,source::permissionForMetric,source.backgroundReadAvailable,source.backgroundReadAvailable && HealthPermission.PERMISSION_READ_HEALTH_DATA_IN_BACKGROUND in granted,onBackgroundPermission)')
screens=java/'PulseScreens.kt'
change(screens,'    navigate:(String)->Unit,openSamsung:()->Unit) {','    navigate:(String)->Unit,openSamsung:()->Unit, permissionForMetric:(String)->String?,\n    backgroundAvailable:Boolean, backgroundEnabled:Boolean, onBackgroundPermission:()->Unit) {')
change(screens,'        item{PulseSection("עוד אפשרויות")}',"""
        item{
            PulseCard(Modifier.fillMaxWidth()){
                Value("סנכרון אוטומטי",size=19)
                Label("בפתיחה וכל 3 דקות כשהאפליקציה פתוחה.")
                Label(if(backgroundEnabled) "סנכרון ברקע מופעל, כ־30 דקות לפי החלטת Android."
                    else if(backgroundAvailable) "סנכרון ברקע דורש הרשאה נוספת."
                    else "קריאה ברקע לא נתמכת ב־Health Connect במכשיר.")
            }
        }
        item{
            if(backgroundAvailable && !backgroundEnabled)
                PulseButton("אפשר סנכרון ברקע",onBackgroundPermission,Modifier.fillMaxWidth(),enabled=available && !busy)
        }
        item{PulseSection("בדיקת מדדים • 30 ימים")}
        items(listOf(Metric.HEART,Metric.OXYGEN,Metric.STEPS,Metric.SLEEP,Metric.ACTIVE_CALORIES,
            Metric.TOTAL_CALORIES,Metric.DISTANCE,Metric.EXERCISE,Metric.WEIGHT,Metric.RESTING_HEART,Metric.BODY_FAT)) { metric ->
            val allowed=permissionForMetric(metric)?.let{it in granted}==true
            val rows=store.entries(metric,30)
            val last=rows.firstOrNull()
            PulseCard(Modifier.fillMaxWidth()){
                Value(Metric.label(metric),size=17)
                if(!allowed) Label("הרשאת Pulse חסרה",color=PulseColors.heart)
                else if(last==null) Label("יש הרשאה אך עדיין אין מדידות מ־Health Connect",color=PulseColors.heart)
                else {
                    Label("נקלטו "+rows.size.toString()+" מדידות • "+timeText(last.time),color=PulseColors.activity)
                    Label("מקור: "+last.origin,size=11)
                }
            }
        }
        item{Label("אם יש הרשאה אך אין נתונים, פתח Samsung Health > הגדרות > Health Connect ובדוק הרשאות כתיבה של Samsung Health. Pulse אינה מפעילה מדידה בשעון.",size=12)}
        item{PulseSection("עוד אפשרויות")}""")
print("Pulse v1.1 patch complete")
