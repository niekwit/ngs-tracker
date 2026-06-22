library(DiffBind)
library(ggplot2)

# Load peak set and count reads
dba <- dba(sampleSheet = "sample_sheet.csv")
dba <- dba.count(dba, bUseSummarizeOverlaps = TRUE)
dba <- dba.normalize(dba)
dba <- dba.contrast(dba, categories = DBA_CONDITION)
dba <- dba.analyze(dba)

# Export results
res <- dba.report(dba, th = 0.05)
write.csv(as.data.frame(res), "differential_peaks.csv", row.names = FALSE)

# MA plot
png("ma_plot.png", width = 800, height = 600, res = 150)
dba.plotMA(dba)
dev.off()
